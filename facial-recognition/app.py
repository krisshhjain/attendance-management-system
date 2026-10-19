"""
Flask microservice for facial enrollment, liveness, and recognition.

This service acts as the internal computer vision backend for the Dailoqa
Attendance Management System. It provides HTTP endpoints consumed by the
Django backend (backend/attendance/face_service.py):
  - /health: Unauthenticated service health probe.
  - /enroll: Averages embeddings from exactly 3 enrollment images.
  - /extract: Extracts a 512-d L2-normalized embedding from a single image.
  - /recognize: Single-frame liveness verification and 1:N candidate matching.
  - /recognize-sequence: Temporal multi-frame liveness gating and 1:N match.

Security model:
  - Default bind host is loopback (127.0.0.1). Non-loopback binds require
    FACE_SERVICE_TOKEN to be configured.
  - Bearer token authentication is enforced on all non-health endpoints.
  - Timing-safe HMAC comparison is used to mitigate side-channel attacks.
  - CSRF is not configured because this is a stateless JSON API without
    browser session cookies.
"""

import base64
import hashlib
import hmac
import io
import ipaddress
import math
import os
import time

import numpy as np

# Import the existing tested face extraction function
from face_utils import FaceExtractionError, extract_primary_face_embedding
from flask import Flask, jsonify, request
from liveness import LivenessInputError, assess_liveness
from PIL import Image

# CSRF protection is intentionally not configured: this JSON API does not use
# browser sessions or cookies, and every non-health endpoint requires an
# explicit Authorization: Bearer token. Browsers do not attach this token
# automatically, so cross-site requests cannot authenticate through ambient
# credentials. Reassess this if cookie/session authentication is introduced.
app = Flask(__name__)
app.config["LIVENESS_DIAGNOSTICS_ENABLED"] = os.environ.get(
    "FR_LIVENESS_DIAGNOSTICS", "0"
).strip().lower() in {"1", "true", "yes", "on"}


def _configured_bind_host():
    """Determine the bind host and enforce authentication for network binds.

    By default, the service binds to loopback (127.0.0.1) for local IPC.
    When configured for external interfaces (e.g. container networking),
    a non-empty FACE_SERVICE_TOKEN is mandatory to prevent unauthorized
    access.
    """
    host = os.environ.get("FR_BIND_HOST", "127.0.0.1").strip() or "127.0.0.1"
    try:
        is_loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        is_loopback = host.casefold() == "localhost"
    if (
        not is_loopback
        and not os.environ.get("FACE_SERVICE_TOKEN", "").strip()
    ):
        raise RuntimeError(
            "FACE_SERVICE_TOKEN is required when FR_BIND_HOST is not loopback."
        )
    return host


@app.before_request
def _authenticate_non_health_requests():
    """Protect the internal API when a shared service token is configured.

    These JSON endpoints have no browser session or cookie authentication, so
    CSRF tokens do not apply. Every non-health request requires explicit
    bearer authentication, including requests arriving over loopback.
    """
    if request.endpoint == "health":
        return None
    token = os.environ.get("FACE_SERVICE_TOKEN", "").strip()
    if not token:
        return jsonify({"error": "Unauthorized"}), 401
    expected = f"Bearer {token}"
    supplied = request.headers.get("Authorization", "")
    if not hmac.compare_digest(supplied, expected):
        return jsonify({"error": "Unauthorized"}), 401
    return None


# Temporal sequence gating constants for multi-frame attendance captures:
# - SEQUENCE_MIN_FRAMES / SEQUENCE_MAX_FRAMES: Enforces 3 to 7 frames per
#   check-in attempt, matching the kiosk/webcam capture capabilities.
# - SEQUENCE_MIN_LIVE_RATIO: At least 80% of frames must be classified as live.
# - SEQUENCE_MIN_SPAN_MS / SEQUENCE_MAX_SPAN_MS: The capture sequence must span
#   between 300ms and 3000ms to guarantee natural motion and prevent bursts of
#   identical frames.
SEQUENCE_MIN_FRAMES = 3
SEQUENCE_MAX_FRAMES = 7
SEQUENCE_MIN_LIVE_RATIO = float(
    os.environ.get("FR_LIVENESS_MIN_LIVE_RATIO", "0.8")
)
SEQUENCE_MIN_SPAN_MS = 300
SEQUENCE_MAX_SPAN_MS = 3000


def _recognize_embedding(query_emb, candidates, threshold):
    """Apply cosine-distance candidate matching against enrolled templates.

    Calculates cosine distance as (1.0 - dot(query_emb, cand_template)).
    Because ArcFace embeddings are L2-normalized unit vectors, the dot product
    equals cosine similarity in [-1.0, 1.0], bounding distance to [0.0, 1.0].
    Smaller distances indicate closer facial similarity.

    Args:
        query_emb: 1D L2-normalized numpy array representing the query face.
        candidates: List of dicts with 'id' (int/str) and 'template' (list).
        threshold: Float maximum cosine distance to qualify as a match
            (default 0.60, corresponding to cosine similarity >= 0.40).

    Returns:
        dict: {"status": "match", "employee_id": ..., "distance": ...} if
        distance <= threshold, else {"status": "unknown", "distance": ...}.
    """
    best_match_id = None
    best_distance = float("inf")
    for candidate in candidates:
        cand_id = candidate.get("id")
        cand_template = candidate.get("template")
        if not cand_id or not cand_template:
            continue
        dist = max(0.0, min(1.0, 1.0 - np.dot(query_emb, cand_template)))
        if dist < best_distance:
            best_distance = dist
            best_match_id = cand_id

    if best_distance <= threshold and best_match_id is not None:
        return {
            "status": "match",
            "employee_id": best_match_id,
            "distance": float(best_distance),
        }
    return {
        "status": "unknown",
        "distance": (
            float(best_distance) if best_distance != float("inf") else None
        ),
    }


def _sequence_diagnostics(
    enabled,
    frame_results,
    final_decision,
    recognition_result,
    latency_ms,
    metadata=None,
):
    """Format optional liveness and recognition diagnostic telemetry.

    When FR_LIVENESS_DIAGNOSTICS is enabled, returns detailed per-frame scores,
    timing, and device context to aid audit logging and model calibration.
    """
    if not enabled:
        return {}
    return {
        "diagnostics": {
            "frame_count": len(frame_results),
            "frames": frame_results,
            "final_liveness": final_decision,
            "recognition_result": recognition_result,
            "total_latency_ms": round(latency_ms, 3),
            "test_case": str((metadata or {}).get("test_case", ""))[:80],
            "device": str((metadata or {}).get("device", ""))[:80],
            "attendance_event_created": (
                (metadata or {}).get("attendance_event_created")
                if isinstance(
                    (metadata or {}).get("attendance_event_created"), bool
                )
                else None
            ),
        }
    }


def _decode_image(b64_string: str) -> np.ndarray:
    """Decode a base64-encoded image string into an RGB numpy array.

    Handles optional Data URL scheme prefix (e.g. 'data:image/jpeg;base64,').
    Uses PIL to ensure standard 3-channel RGB orientation regardless of source
    format (JPEG, PNG, etc.).

    Raises:
        FaceExtractionError: If the base64 string is corrupted or unreadable.
    """
    try:
        if b64_string.startswith("data:image"):
            b64_string = b64_string.split(",", 1)[1]

        image_bytes = base64.b64decode(b64_string)
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return np.array(image)
    except Exception as e:
        raise FaceExtractionError(f"Failed to decode image: {e}")


@app.route("/health", methods=["GET"])
def health():
    """Unauthenticated health probe for container orchestration."""
    return jsonify({"status": "ok"}), 200


@app.route("/enroll", methods=["POST"])
def enroll():
    """Extract and average embeddings across 3 distinct enrollment images.

    Expected JSON body:
        {"images": [<b64_image_1>, <b64_image_2>, <b64_image_3>]}

    Pipeline:
      1. Validates that exactly 3 images are provided.
      2. Extracts 512-d ArcFace embedding from each with min_confidence=0.95.
      3. Computes the mean embedding across all 3 vectors.
      4. Re-normalizes the mean vector with L2 norm to preserve unit length.

    Returns:
        JSON with 'template' containing the 512-d float list on HTTP 200,
        or 400/500 error payload on extraction/validation failure.
    """
    data = request.json
    if not data or "images" not in data:
        return jsonify({"error": "Missing 'images' field"}), 400

    images = data["images"]
    if not isinstance(images, list) or len(images) != 3:
        return jsonify({"error": "Enrollment requires exactly 3 images"}), 400

    try:
        embeddings = []
        for b64_img in images:
            img_array = _decode_image(b64_img)
            emb = extract_primary_face_embedding(
                img_array, min_confidence=0.95
            )
            embeddings.append(emb)

        avg_embedding = np.mean(embeddings, axis=0)
        norm = np.linalg.norm(avg_embedding)
        if norm > 0:
            avg_embedding = avg_embedding / norm

        return jsonify({"template": avg_embedding.tolist()}), 200

    except FaceExtractionError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Internal server error: {e}"}), 500


@app.route("/extract", methods=["POST"])
def extract():
    """Extract a 512-d L2-normalized ArcFace embedding from a single image.

    Expected JSON body:
        {"image": "<base64_string>"}

    Returns:
        JSON with 'embedding' containing the 512-d float list on HTTP 200.
    """
    data = request.json
    if not data or "image" not in data:
        return jsonify({"error": "Missing 'image' field"}), 400

    try:
        img_array = _decode_image(data["image"])
        emb = extract_primary_face_embedding(img_array, min_confidence=0.95)
        return jsonify({"embedding": emb.tolist()}), 200
    except FaceExtractionError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Internal server error: {e}"}), 500


@app.route("/recognize", methods=["POST"])
def recognize():
    """Perform 1:N face identification with single-frame liveness gating.

    Pipeline:
      1. Decodes base64 RGB image.
      2. Assesses presentation-attack liveness via MiniFASNet. Rejects if
         spoof is detected (HTTP 400) or fails closed if runtime errors occur
         (HTTP 503).
      3. Extracts 512-d primary face embedding via RetinaFace + ArcFace.
      4. Compares query embedding against all candidate templates via cosine
         distance.
      5. Returns match if best_distance <= threshold, else unknown.
    """
    data = request.json
    if not data or "image" not in data or "candidates" not in data:
        return jsonify({"error": "Missing 'image' or 'candidates' field"}), 400

    threshold = data.get("threshold", 0.60)
    candidates = data["candidates"]

    try:
        # Extract query embedding
        img_array = _decode_image(data["image"])
        try:
            liveness = assess_liveness(img_array)
        except LivenessInputError as e:
            # Preserve the existing no-face/multi-face error response shape.
            return jsonify({"error": str(e)}), 400
        except Exception:
            app.logger.exception("Liveness assessment failed")
            return (
                jsonify(
                    {
                        "status": "liveness_error",
                        "error": "Liveness assessment failed",
                    }
                ),
                503,
            )
        if not liveness.is_live:
            return (
                jsonify(
                    {
                        "status": "liveness_failed",
                        "reason": liveness.reason,
                    }
                ),
                400,
            )
        query_emb = extract_primary_face_embedding(
            img_array, min_confidence=0.95
        )

        # Match against candidates
        best_match_id = None
        best_distance = float("inf")

        for candidate in candidates:
            cand_id = candidate.get("id")
            cand_template = candidate.get("template")
            if not cand_id or not cand_template:
                continue

            # Compute cosine distance: 1 - dot_product
            # Assuming vectors are already L2 normalized
            dist = max(0.0, min(1.0, 1.0 - np.dot(query_emb, cand_template)))

            if dist < best_distance:
                best_distance = dist
                best_match_id = cand_id

        if best_distance <= threshold and best_match_id is not None:
            return (
                jsonify(
                    {
                        "status": "match",
                        "employee_id": best_match_id,
                        "distance": float(best_distance),
                    }
                ),
                200,
            )
        else:
            return (
                jsonify(
                    {
                        "status": "unknown",
                        "distance": (
                            float(best_distance)
                            if best_distance != float("inf")
                            else None
                        ),
                    }
                ),
                200,
            )

    except FaceExtractionError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Internal server error: {e}"}), 500


@app.route("/recognize-sequence", methods=["POST"])
def recognize_sequence():
    """Gate 1:N face recognition on a temporal sequence of RGB frames.

    Designed for kiosk and mobile check-in flows where presentation attacks
    (screens, paper printouts, video replays) must be detected before
    running ArcFace recognition.

    Expected JSON body:
        {
            "frames": ["<b64_frame_1>", "<b64_frame_2>", ...],
            "captured_at_ms": [1000, 1500, 2000, ...],
            "candidates": [{"id": ..., "template": [...]}, ...],
            "threshold": 0.60  # optional, default 0.60
        }

    Sequence validation rules:
      - 3 to 7 frames required.
      - Exactly one millisecond timestamp per frame.
      - Timestamps must be strictly monotonically increasing.
      - Sequence duration (last - first) must span 300ms to 3000ms.

    Liveness gating:
      - Every unique frame is evaluated with MiniFASNet.
      - Duplicate frames (detected via SHA-256 byte hashing) are ignored.
      - Requires at least ceil(N * SEQUENCE_MIN_LIVE_RATIO) live frames.
      - If passed, selects the temporally central live frame for ArcFace
        embedding extraction and 1:N candidate matching.
    """
    started = time.perf_counter()
    data = request.json
    if not data or "frames" not in data or "candidates" not in data:
        return (
            jsonify({"error": "Missing 'frames' or 'candidates' field"}),
            400,
        )

    frames = data["frames"]
    timestamps = data.get("captured_at_ms")
    candidates = data["candidates"]
    if (
        not isinstance(frames, list)
        or not SEQUENCE_MIN_FRAMES <= len(frames) <= SEQUENCE_MAX_FRAMES
    ):
        return (
            jsonify({
                "status":
                "liveness_failed",
                "reason":
                "insufficient-frames",
                "error":
                f"A sequence must contain {SEQUENCE_MIN_FRAMES}-"
                    f"{SEQUENCE_MAX_FRAMES} frames",
            }),
            400,
        )
    if not isinstance(candidates, list):
        return jsonify({"error": "'candidates' must be a list"}), 400
    if not all(isinstance(frame, str) and frame for frame in frames):
        return (
            jsonify({"status": "liveness_failed", "reason": "invalid-frame"}),
            400,
        )
    if (
        not isinstance(timestamps, list)
        or len(timestamps) != len(frames)
        or not all(
            isinstance(value, (int, float)) and math.isfinite(value)
            for value in timestamps
        )
        or any(
            right <= left for left, right in zip(timestamps, timestamps[1:])
        )
        or timestamps[-1] - timestamps[0] < SEQUENCE_MIN_SPAN_MS
        or timestamps[-1] - timestamps[0] > SEQUENCE_MAX_SPAN_MS
    ):
        return (
            jsonify(
                {"status": "liveness_failed", "reason": "invalid-frame-timing"}
            ),
            400,
        )
    if (
        not math.isfinite(SEQUENCE_MIN_LIVE_RATIO)
        or not 0.5 < SEQUENCE_MIN_LIVE_RATIO <= 1.0
    ):
        app.logger.error("Invalid FR_LIVENESS_MIN_LIVE_RATIO configuration")
        return (
            jsonify(
                {
                    "status": "liveness_error",
                    "error": "Liveness configuration is invalid",
                }
            ),
            503,
        )

    diagnostics_enabled = app.config["LIVENESS_DIAGNOSTICS_ENABLED"]
    per_frame = []
    decoded_frames = []
    live_indices = []
    frame_hashes = set()
    try:
        for index, encoded_frame in enumerate(frames):
            try:
                image = _decode_image(encoded_frame)
            except FaceExtractionError:
                return (
                    jsonify(
                        {
                            "status": "liveness_failed",
                            "reason": "invalid-frame",
                            **_sequence_diagnostics(
                                diagnostics_enabled,
                                per_frame,
                                "failed",
                                "not_run",
                                (time.perf_counter() - started) * 1000,
                                data,
                            ),
                        }
                    ),
                    400,
                )

            decoded_frames.append(image)
            # Detect frozen video or duplicate camera frames via SHA-256 digest
            frame_hash = hashlib.sha256(image.tobytes()).digest()
            if frame_hash in frame_hashes:
                frame_result = {"index": index, "result": "duplicate"}
                if diagnostics_enabled:
                    frame_result["reason"] = "duplicate-frame"
                per_frame.append(frame_result)
                continue
            frame_hashes.add(frame_hash)
            frame_started = time.perf_counter()
            try:
                result = assess_liveness(image)
                frame_live = bool(result.is_live)
                frame_result = {
                    "index": index,
                    "result": "live" if frame_live else "spoof",
                }
                if diagnostics_enabled:
                    frame_result["real_score"] = result.real_score
                    frame_result["reason"] = result.reason
                    frame_result["latency_ms"] = round(
                        (time.perf_counter() - frame_started) * 1000, 3
                    )
                per_frame.append(frame_result)
                if frame_live:
                    live_indices.append(index)
            except LivenessInputError:
                frame_result = {"index": index, "result": "unusable"}
                if diagnostics_enabled:
                    frame_result["reason"] = "face-unusable"
                    frame_result["latency_ms"] = round(
                        (time.perf_counter() - frame_started) * 1000, 3
                    )
                per_frame.append(frame_result)
            except Exception:
                if diagnostics_enabled:
                    per_frame.append(
                        {
                            "index": index,
                            "result": "error",
                            "latency_ms": round(
                                (time.perf_counter() - frame_started) * 1000, 3
                            ),
                        }
                    )
                app.logger.exception("Sequence liveness assessment failed")
                return (
                    jsonify(
                        {
                            "status": "liveness_error",
                            "error": "Liveness assessment failed",
                            **_sequence_diagnostics(
                                diagnostics_enabled,
                                per_frame,
                                "error",
                                "not_run",
                                (time.perf_counter() - started) * 1000,
                                data,
                            ),
                        }
                    ),
                    503,
                )

        # Enforce minimum live ratio across the sequence (e.g. >= 80% live)
        required_live = math.ceil(len(frames) * SEQUENCE_MIN_LIVE_RATIO)
        passed = len(live_indices) >= required_live
        if not passed:
            return (
                jsonify(
                    {
                        "status": "liveness_failed",
                        "reason": (
                            "sequence-inconsistent"
                            if live_indices
                            else "spoof-detected"
                        ),
                        **_sequence_diagnostics(
                            diagnostics_enabled,
                            per_frame,
                            "failed",
                            "not_run",
                            (time.perf_counter() - started) * 1000,
                            data,
                        ),
                    }
                ),
                400,
            )

        # Select the temporally central live frame so recognition uses a stable
        # frontal frame, avoiding transitional edges from the start/end of the
        # sequence. ArcFace extraction and 1:N candidate matching then proceed.
        center = (len(frames) - 1) / 2
        recognition_index = min(
            live_indices, key=lambda idx: abs(idx - center)
        )
        query_emb = extract_primary_face_embedding(
            decoded_frames[recognition_index], min_confidence=0.95
        )
        recognition = _recognize_embedding(
            query_emb, candidates, data.get("threshold", 0.60)
        )
        response_data = dict(recognition)
        response_data.update(
            _sequence_diagnostics(
                diagnostics_enabled,
                per_frame,
                "passed",
                recognition["status"],
                (time.perf_counter() - started) * 1000,
                data,
            )
        )
        return jsonify(response_data), 200
    except FaceExtractionError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        app.logger.exception("Sequence recognition failed")
        return jsonify({"error": "Internal server error"}), 500


if __name__ == "__main__":
    # Start the Flask app on port 8001
    app.run(host=_configured_bind_host(), port=8001)
