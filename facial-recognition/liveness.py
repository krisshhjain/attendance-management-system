"""CPU MiniFASNet face presentation-attack detection for the FR service."""

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import onnxruntime as ort


_MODEL_DIR = Path(__file__).resolve().parent / "models"
_ANTISPOOF_MODEL = _MODEL_DIR / "mini_fas_best_model_quantized.onnx"
_FACE_DETECTOR_MODEL = _MODEL_DIR / "mini_fas_detector_quantized.onnx"
_INPUT_SIZE = 128
# Provisional score boundary; default preserves the existing MiniFASNet rule.
# Set FR_LIVENESS_REAL_LOGIT_THRESHOLD only during controlled calibration.
_REAL_LOGIT_THRESHOLD = float(os.environ.get("FR_LIVENESS_REAL_LOGIT_THRESHOLD", "0.0"))


@dataclass(frozen=True)
class LivenessResult:
    is_live: bool
    reason: str
    real_score: Optional[float] = None


class LivenessInputError(ValueError):
    """A decoded image has no usable face crop or contains ambiguous faces."""


@lru_cache(maxsize=1)
def _load_runtime():
    """Load the quantized ONNX classifier and YuNet crop detector once."""
    for model_path in (_ANTISPOOF_MODEL, _FACE_DETECTOR_MODEL):
        if not model_path.is_file():
            raise RuntimeError(f"Required liveness model is missing: {model_path.name}")

    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    classifier = ort.InferenceSession(
        str(_ANTISPOOF_MODEL), sess_options=options, providers=["CPUExecutionProvider"]
    )
    # A lower detector floor retains dim/glasses faces; the anti-spoof
    # classifier still decides live versus spoof, and missing detections fail closed.
    detector = cv2.FaceDetectorYN.create(
        str(_FACE_DETECTOR_MODEL), "", (320, 320), 0.2, 0.3, 5000
    )

    inputs = classifier.get_inputs()
    outputs = classifier.get_outputs()
    if len(inputs) != 1 or len(outputs) != 1:
        raise RuntimeError("Unexpected MiniFASNet ONNX input/output contract")
    return detector, classifier, inputs[0].name


def _largest_face_crop(rgb_image: np.ndarray, detector) -> tuple[np.ndarray, int]:
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
    if len(boxes) > 1 and boxes[1][0] / max(largest[0], 1) >= (1.0 / 1.5):
        raise LivenessInputError("Ambiguous multi-face image")

    _, x1, y1, x2, y2 = largest
    face_width, face_height = x2 - x1, y2 - y1
    side = int(max(face_width, face_height) * 1.5)
    center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
    crop_x1, crop_y1 = center_x - side // 2, center_y - side // 2
    crop_x2, crop_y2 = crop_x1 + side, crop_y1 + side

    pad_left, pad_top = max(0, -crop_x1), max(0, -crop_y1)
    pad_right, pad_bottom = max(0, crop_x2 - width), max(0, crop_y2 - height)
    crop = rgb_image[max(0, crop_y1):min(height, crop_y2),
                     max(0, crop_x1):min(width, crop_x2)]
    if any((pad_left, pad_top, pad_right, pad_bottom)):
        crop = cv2.copyMakeBorder(
            crop, pad_top, pad_bottom, pad_left, pad_right, cv2.BORDER_REFLECT_101
        )
    if crop.size == 0:
        raise ValueError("Unable to crop detected face")
    return crop, len(boxes)


def assess_liveness(image: np.ndarray) -> LivenessResult:
    """Classify one decoded RGB frame; runtime failures are raised to fail closed."""
    if image is None or image.size == 0:
        raise ValueError("Empty image provided to liveness assessment")
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("Liveness assessment requires an RGB image")

    detector, classifier, input_name = _load_runtime()
    face_crop, _ = _largest_face_crop(image, detector)
    resized = cv2.resize(face_crop, (_INPUT_SIZE, _INPUT_SIZE), interpolation=cv2.INTER_AREA)
    tensor = (resized.astype(np.float32) / 255.0).transpose(2, 0, 1)[None, ...]
    logits = np.asarray(classifier.run(None, {input_name: tensor})[0], dtype=np.float32)
    if logits.shape != (1, 2) or not np.isfinite(logits).all():
        raise RuntimeError("MiniFASNet returned invalid scores")

    # Model's documented class order is [real, spoof].
    real_score = float(logits[0, 0] - logits[0, 1])
    is_live = real_score >= _REAL_LOGIT_THRESHOLD
    return LivenessResult(
        is_live=is_live,
        reason="live" if is_live else "spoof-detected",
        real_score=real_score,
    )
