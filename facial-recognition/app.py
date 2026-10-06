import os
import io
import base64
import hashlib
import math
import numpy as np
import time
from PIL import Image
from flask import Flask, request, jsonify

# Import the existing tested face extraction function
from face_utils import extract_primary_face_embedding, FaceExtractionError
from liveness import assess_liveness, LivenessInputError

app = Flask(__name__)
app.config["LIVENESS_DIAGNOSTICS_ENABLED"] = os.environ.get(
    "FR_LIVENESS_DIAGNOSTICS", "0"
).strip().lower() in {"1", "true", "yes", "on"}

SEQUENCE_MIN_FRAMES = 3
SEQUENCE_MAX_FRAMES = 7
SEQUENCE_MIN_LIVE_RATIO = float(os.environ.get("FR_LIVENESS_MIN_LIVE_RATIO", "0.8"))
SEQUENCE_MIN_SPAN_MS = 300
SEQUENCE_MAX_SPAN_MS = 3000


def _recognize_embedding(query_emb, candidates, threshold):
    """Apply the existing cosine-distance candidate matching behavior."""
    best_match_id = None
    best_distance = float('inf')
    for candidate in candidates:
        cand_id = candidate.get('id')
        cand_template = candidate.get('template')
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
        "distance": float(best_distance) if best_distance != float('inf') else None,
    }


def _sequence_diagnostics(enabled, frame_results, final_decision, recognition_result, latency_ms, metadata=None):
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
            "attendance_event_created": (metadata or {}).get("attendance_event_created")
            if isinstance((metadata or {}).get("attendance_event_created"), bool) else None,
        }
    }

def _decode_image(b64_string: str) -> np.ndarray:
    """Helper to decode base64 into a numpy array."""
    try:
        if b64_string.startswith('data:image'):
            b64_string = b64_string.split(',', 1)[1]
            
        image_bytes = base64.b64decode(b64_string)
        image = Image.open(io.BytesIO(image_bytes)).convert('RGB')
        return np.array(image)
    except Exception as e:
        raise FaceExtractionError(f"Failed to decode image: {e}")

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

@app.route('/enroll', methods=['POST'])
def enroll():
    data = request.json
    if not data or 'images' not in data:
        return jsonify({"error": "Missing 'images' field"}), 400
        
    images = data['images']
    if not isinstance(images, list) or len(images) != 3:
        return jsonify({"error": "Enrollment requires exactly 3 images"}), 400
        
    try:
        embeddings = []
        for b64_img in images:
            img_array = _decode_image(b64_img)
            emb = extract_primary_face_embedding(img_array, min_confidence=0.95)
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

@app.route('/extract', methods=['POST'])
def extract():
    """Extracts embedding from a single image."""
    data = request.json
    if not data or 'image' not in data:
        return jsonify({"error": "Missing 'image' field"}), 400
        
    try:
        img_array = _decode_image(data['image'])
        emb = extract_primary_face_embedding(img_array, min_confidence=0.95)
        return jsonify({"embedding": emb.tolist()}), 200
    except FaceExtractionError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Internal server error: {e}"}), 500

@app.route('/recognize', methods=['POST'])
def recognize():
    """Performs 1:N recognition against provided candidates."""
    data = request.json
    if not data or 'image' not in data or 'candidates' not in data:
        return jsonify({"error": "Missing 'image' or 'candidates' field"}), 400
        
    threshold = data.get('threshold', 0.60)
    candidates = data['candidates']
    
    try:
        # Extract query embedding
        img_array = _decode_image(data['image'])
        try:
            liveness = assess_liveness(img_array)
        except LivenessInputError as e:
            # Preserve the existing no-face/multi-face error response shape.
            return jsonify({"error": str(e)}), 400
        except Exception:
            app.logger.exception("Liveness assessment failed")
            return jsonify({
                "status": "liveness_error",
                "error": "Liveness assessment failed",
            }), 503
        if not liveness.is_live:
            return jsonify({
                "status": "liveness_failed",
                "reason": liveness.reason,
            }), 400
        query_emb = extract_primary_face_embedding(img_array, min_confidence=0.95)
        
        # Match against candidates
        best_match_id = None
        best_distance = float('inf')
        
        for candidate in candidates:
            cand_id = candidate.get('id')
            cand_template = candidate.get('template')
            if not cand_id or not cand_template:
                continue
                
            # Compute cosine distance: 1 - dot_product
            # Assuming vectors are already L2 normalized
            dist = max(0.0, min(1.0, 1.0 - np.dot(query_emb, cand_template)))
            
            if dist < best_distance:
                best_distance = dist
                best_match_id = cand_id
                
        if best_distance <= threshold and best_match_id is not None:
            return jsonify({
                "status": "match",
                "employee_id": best_match_id,
                "distance": float(best_distance)
            }), 200
        else:
            return jsonify({
                "status": "unknown",
                "distance": float(best_distance) if best_distance != float('inf') else None
            }), 200
            
    except FaceExtractionError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Internal server error: {e}"}), 500


@app.route('/recognize-sequence', methods=['POST'])
def recognize_sequence():
    """Gate recognition on a short, ordered sequence of RGB camera frames."""
    started = time.perf_counter()
    data = request.json
    if not data or 'frames' not in data or 'candidates' not in data:
        return jsonify({"error": "Missing 'frames' or 'candidates' field"}), 400

    frames = data['frames']
    timestamps = data.get('captured_at_ms')
    candidates = data['candidates']
    if not isinstance(frames, list) or not SEQUENCE_MIN_FRAMES <= len(frames) <= SEQUENCE_MAX_FRAMES:
        return jsonify({
            "status": "liveness_failed",
            "reason": "insufficient-frames",
            "error": f"A sequence must contain {SEQUENCE_MIN_FRAMES}-{SEQUENCE_MAX_FRAMES} frames",
        }), 400
    if not isinstance(candidates, list):
        return jsonify({"error": "'candidates' must be a list"}), 400
    if not all(isinstance(frame, str) and frame for frame in frames):
        return jsonify({"status": "liveness_failed", "reason": "invalid-frame"}), 400
    if (not isinstance(timestamps, list) or len(timestamps) != len(frames)
            or not all(isinstance(value, (int, float)) and math.isfinite(value) for value in timestamps)
            or any(right <= left for left, right in zip(timestamps, timestamps[1:]))
            or timestamps[-1] - timestamps[0] < SEQUENCE_MIN_SPAN_MS
            or timestamps[-1] - timestamps[0] > SEQUENCE_MAX_SPAN_MS):
        return jsonify({"status": "liveness_failed", "reason": "invalid-frame-timing"}), 400
    if not math.isfinite(SEQUENCE_MIN_LIVE_RATIO) or not 0.5 < SEQUENCE_MIN_LIVE_RATIO <= 1.0:
        app.logger.error("Invalid FR_LIVENESS_MIN_LIVE_RATIO configuration")
        return jsonify({"status": "liveness_error", "error": "Liveness configuration is invalid"}), 503

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
                return jsonify({
                    "status": "liveness_failed",
                    "reason": "invalid-frame",
                    **_sequence_diagnostics(
                        diagnostics_enabled, per_frame, "failed", "not_run",
                        (time.perf_counter() - started) * 1000, data,
                    ),
                }), 400

            decoded_frames.append(image)
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
                    frame_result["latency_ms"] = round((time.perf_counter() - frame_started) * 1000, 3)
                per_frame.append(frame_result)
                if frame_live:
                    live_indices.append(index)
            except LivenessInputError:
                frame_result = {"index": index, "result": "unusable"}
                if diagnostics_enabled:
                    frame_result["reason"] = "face-unusable"
                    frame_result["latency_ms"] = round((time.perf_counter() - frame_started) * 1000, 3)
                per_frame.append(frame_result)
            except Exception:
                if diagnostics_enabled:
                    per_frame.append({
                        "index": index,
                        "result": "error",
                        "latency_ms": round((time.perf_counter() - frame_started) * 1000, 3),
                    })
                app.logger.exception("Sequence liveness assessment failed")
                return jsonify({
                    "status": "liveness_error",
                    "error": "Liveness assessment failed",
                    **_sequence_diagnostics(
                        diagnostics_enabled, per_frame, "error", "not_run",
                        (time.perf_counter() - started) * 1000, data,
                    ),
                }), 503

        required_live = math.ceil(len(frames) * SEQUENCE_MIN_LIVE_RATIO)
        passed = len(live_indices) >= required_live
        if not passed:
            return jsonify({
                "status": "liveness_failed",
                "reason": "sequence-inconsistent" if live_indices else "spoof-detected",
                **_sequence_diagnostics(
                    diagnostics_enabled, per_frame, "failed", "not_run",
                    (time.perf_counter() - started) * 1000, data,
                ),
            }), 400

        # Use the temporally central passing frame so recognition sees a normal
        # camera frame; ArcFace extraction and candidate matching stay unchanged.
        center = (len(frames) - 1) / 2
        recognition_index = min(live_indices, key=lambda idx: abs(idx - center))
        query_emb = extract_primary_face_embedding(decoded_frames[recognition_index], min_confidence=0.95)
        recognition = _recognize_embedding(query_emb, candidates, data.get('threshold', 0.60))
        response_data = dict(recognition)
        response_data.update(_sequence_diagnostics(
            diagnostics_enabled, per_frame, "passed", recognition["status"],
            (time.perf_counter() - started) * 1000, data,
        ))
        return jsonify(response_data), 200
    except FaceExtractionError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        app.logger.exception("Sequence recognition failed")
        return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    # Start the Flask app on port 8001
    app.run(host='0.0.0.0', port=8001)
