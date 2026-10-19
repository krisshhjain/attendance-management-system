"""
CPU MiniFASNet face presentation-attack detection for the FR service.

This module implements two-stage presentation-attack detection (anti-spoofing)
to prevent attendance fraud via printed photos, screen replays, or masks:
  1. Face Detection: OpenCV YuNet ONNX detector locates face bounding boxes
     in the input RGB frame.
  2. Anti-Spoof Classification: MiniFASNet quantized ONNX model evaluates an
     expanded face crop to determine whether the subject is live or spoof.

Execution characteristics:
  - Runs entirely on CPU via onnxruntime CPUExecutionProvider.
  - Thread pools are restricted (intra_op=1, inter_op=1) for predictable
    CPU utilization within containerized worker processes.
  - Runtime models are cached via @lru_cache(maxsize=1) after first load.
  - If detection or classification fails, exceptions fail closed.
"""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import onnxruntime as ort

# Paths to quantized ONNX model weights in the local models/ directory
_MODEL_DIR = Path(__file__).resolve().parent / "models"
_ANTISPOOF_MODEL = _MODEL_DIR / "mini_fas_best_model_quantized.onnx"
_FACE_DETECTOR_MODEL = _MODEL_DIR / "mini_fas_detector_quantized.onnx"

# Expected input dimension for the MiniFASNet anti-spoof classifier (128x128)
_INPUT_SIZE = 128

# Decision threshold for the logit difference: (real_logit - spoof_logit).
# A threshold of 0.0 corresponds to argmax classification (real > spoof).
# Configurable via environment variable for controlled empirical calibration.
_REAL_LOGIT_THRESHOLD = float(
    os.environ.get("FR_LIVENESS_REAL_LOGIT_THRESHOLD", "0.0")
)


@dataclass(frozen=True)
class LivenessResult:
    """Immutable result structure for single-frame liveness evaluation.

    Attributes:
        is_live: True if the real score meets or exceeds the threshold.
        reason: Diagnostic string ('live', 'spoof-detected', etc.).
        real_score: Difference between real and spoof model logits.
    """
    is_live: bool
    reason: str
    real_score: Optional[float] = None


class LivenessInputError(ValueError):
    """Raised when an image has no detectable face or ambiguous multi-faces."""


@lru_cache(maxsize=1)
def _load_runtime():
    """Load and initialize ONNX runtime sessions and detectors once.

    Configures single-threaded CPU execution for predictable resource usage
    in containerized microservice deployments. Uses cv2.FaceDetectorYN for
    fast YuNet face detection with a permissive detection floor (0.2) to
    avoid dropping faces in low light or with eyeglasses.
    """
    for model_path in (_ANTISPOOF_MODEL, _FACE_DETECTOR_MODEL):
        if not model_path.is_file():
            raise RuntimeError(
                f"Required liveness model is missing: {model_path.name}"
            )

    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    classifier = ort.InferenceSession(
        str(_ANTISPOOF_MODEL),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    # A lower detector floor retains dim/glasses faces; the anti-spoof
    # classifier still decides live versus spoof, and missing detections fail
    # closed.
    detector = cv2.FaceDetectorYN.create(
        str(_FACE_DETECTOR_MODEL), "", (320, 320), 0.2, 0.3, 5000
    )

    inputs = classifier.get_inputs()
    outputs = classifier.get_outputs()
    if len(inputs) != 1 or len(outputs) != 1:
        raise RuntimeError("Unexpected MiniFASNet ONNX input/output contract")
    return detector, classifier, inputs[0].name


def _largest_face_crop(
    rgb_image: np.ndarray, detector
) -> tuple[np.ndarray, int]:
    """Detect and extract the primary face crop with context padding.

    Uses YuNet (FaceDetectorYN) on BGR-converted input to locate all faces.
    Selects the largest face bounding box by area. Enforces ambiguity
    rejection if the second largest face is within 1.5x area of the
    primary face.

    Expands the crop region by 1.5x around the center point to include
    surrounding context (hairline, ears, chin, background) required by
    MiniFASNet to detect presentation-attack artifacts (e.g. tablet borders).
    Applies BORDER_REFLECT_101 padding when the crop extends beyond image
    bounds.

    Returns:
        tuple: (square_rgb_crop_array, total_detected_face_count).

    Raises:
        LivenessInputError: If no face is found or faces are ambiguously sized.
        ValueError: If crop extraction produces an empty array.
    """
    height, width = rgb_image.shape[:2]
    bgr_image = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)
    detector.setInputSize((width, height))
    _, faces = detector.detect(bgr_image)
    if faces is None or len(faces) == 0:
        raise LivenessInputError("No faces detected")

    boxes = []
    for face in faces:
        x, y, box_width, box_height = (int(v) for v in face[:4])
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(width, x + box_width), min(height, y + box_height)
        if x2 > x1 and y2 > y1:
            boxes.append((box_width * box_height, x1, y1, x2, y2))
    if not boxes:
        raise LivenessInputError("No faces detected")

    boxes.sort(reverse=True)
    largest = boxes[0]
    # Disambiguation threshold: fail closed if second face is similar in scale
    if len(boxes) > 1 and boxes[1][0] / max(largest[0], 1) >= (1.0 / 1.5):
        raise LivenessInputError("Ambiguous multi-face image")

    _, x1, y1, x2, y2 = largest
    face_width, face_height = x2 - x1, y2 - y1
    # 1.5x expansion around face center provides anti-spoof context
    side = int(max(face_width, face_height) * 1.5)
    center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
    crop_x1, crop_y1 = center_x - side // 2, center_y - side // 2
    crop_x2, crop_y2 = crop_x1 + side, crop_y1 + side

    # Reflect border pixels if context box exceeds image boundaries
    pad_left, pad_top = max(0, -crop_x1), max(0, -crop_y1)
    pad_right, pad_bottom = max(0, crop_x2 - width), max(0, crop_y2 - height)
    crop = rgb_image[
        max(0, crop_y1):min(height, crop_y2),
        max(0, crop_x1):min(width, crop_x2),
    ]
    if any((pad_left, pad_top, pad_right, pad_bottom)):
        crop = cv2.copyMakeBorder(
            crop,
            pad_top,
            pad_bottom,
            pad_left,
            pad_right,
            cv2.BORDER_REFLECT_101,
        )
    if crop.size == 0:
        raise ValueError("Unable to crop detected face")
    return crop, len(boxes)


def assess_liveness(image: np.ndarray) -> LivenessResult:
    """Classify presentation-attack liveness for a single decoded RGB frame.

    Pipeline:
      1. Validates image dimensions and 3-channel RGB format.
      2. Detects face and extracts 1.5x contextual crop via YuNet.
      3. Resizes crop to 128x128 (INTER_AREA) and normalizes pixel values to
         [0.0, 1.0] in NCHW format: shape (1, 3, 128, 128).
      4. Executes ONNX inference with MiniFASNet to obtain classification
         logits of shape (1, 2) where class 0 is 'real' and class 1 is 'spoof'.
      5. Computes real_score = (real_logit - spoof_logit).
      6. Evaluates is_live = (real_score >= _REAL_LOGIT_THRESHOLD).

    Returns:
        LivenessResult: Named tuple containing is_live, reason string,
        and real_score.

    Raises:
        LivenessInputError: If face detection fails or multiple faces conflict.
        ValueError: On empty or malformed image array.
        RuntimeError: If ONNX model output contract is violated.
    """
    if image is None or image.size == 0:
        raise ValueError("Empty image provided to liveness assessment")
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Liveness assessment requires an RGB image")

    detector, classifier, input_name = _load_runtime()
    face_crop, _ = _largest_face_crop(image, detector)
    resized = cv2.resize(
        face_crop, (_INPUT_SIZE, _INPUT_SIZE), interpolation=cv2.INTER_AREA
    )
    # Convert HWC uint8 [0, 255] to NCHW float32 [0.0, 1.0] for MiniFASNet ONNX
    tensor = (resized.astype(np.float32) / 255.0).transpose(2, 0, 1)[None, ...]
    logits = np.asarray(
        classifier.run(None, {input_name: tensor})[0], dtype=np.float32
    )
    if logits.shape != (1, 2) or not np.isfinite(logits).all():
        raise RuntimeError("MiniFASNet returned invalid scores")

    # MiniFASNet documented class order is index 0: real, index 1: spoof
    real_score = float(logits[0, 0] - logits[0, 1])
    is_live = real_score >= _REAL_LOGIT_THRESHOLD
    return LivenessResult(
        is_live=is_live,
        reason="live" if is_live else "spoof-detected",
        real_score=real_score,
    )
