import unittest
from unittest.mock import patch

import numpy as np

from face_utils import (
    FaceExtractionError,
    extract_primary_face_embedding,
    get_face_count,
    get_face_details,
)


class FaceUtilityTests(unittest.TestCase):
    @patch("face_utils.DeepFace.represent")
    def test_single_embedding_is_l2_normalized_and_detection_is_enforced(self, represent):
        represent.return_value = [{"embedding": [3.0, 4.0], "face_confidence": 0.99}]

        result = extract_primary_face_embedding("portrait.jpg")

        np.testing.assert_allclose(result, [0.6, 0.8])
        self.assertEqual(result.dtype, np.float32)
        self.assertTrue(represent.call_args.kwargs["enforce_detection"])

    @patch("face_utils.DeepFace.represent")
    def test_multiple_faces_selects_largest_unambiguous_face(self, represent):
        represent.return_value = [
            {"embedding": [0.0, 1.0], "facial_area": {"w": 20, "h": 20}},
            {"embedding": [3.0, 4.0], "facial_area": {"w": 60, "h": 60}},
        ]

        result = extract_primary_face_embedding("group.jpg")

        np.testing.assert_allclose(result, [0.6, 0.8])

    @patch("face_utils.DeepFace.represent")
    def test_ambiguous_faces_and_low_confidence_fail_closed(self, represent):
        represent.return_value = [
            {"embedding": [1.0], "facial_area": {"w": 40, "h": 40}},
            {"embedding": [0.0], "facial_area": {"w": 35, "h": 40}},
        ]
        with self.assertRaisesRegex(FaceExtractionError, "Ambiguous multi-face"):
            extract_primary_face_embedding("group.jpg")

        represent.return_value = [{"embedding": [1.0], "face_confidence": 0.2}]
        with self.assertRaisesRegex(FaceExtractionError, "quality too low"):
            extract_primary_face_embedding("blurry.jpg")

    @patch("face_utils.DeepFace.represent")
    def test_zero_embedding_is_rejected_when_normalization_is_requested(self, represent):
        represent.return_value = [{"embedding": [0.0, 0.0]}]
        with self.assertRaisesRegex(FaceExtractionError, "Zero-norm"):
            extract_primary_face_embedding("empty-face.jpg")

    @patch("face_utils.DeepFace.represent")
    def test_detection_failures_and_empty_results_are_reported(self, represent):
        represent.side_effect = RuntimeError("malformed image")
        with self.assertRaisesRegex(FaceExtractionError, "RuntimeError"):
            extract_primary_face_embedding("broken.jpg")
        represent.side_effect = None
        represent.return_value = []
        with self.assertRaisesRegex(FaceExtractionError, "No faces detected"):
            extract_primary_face_embedding("blank.jpg")

    @patch("face_utils.DeepFace.represent")
    def test_face_count_and_details_return_safe_results(self, represent):
        represent.return_value = [
            {"facial_area": {"w": 12, "h": 8}, "face_confidence": 0.98}
        ]
        self.assertEqual(get_face_count("portrait.jpg"), 1)
        self.assertEqual(get_face_details("portrait.jpg"), [{
            "face_index": 0,
            "facial_area": {"w": 12, "h": 8},
            "area": 96,
            "confidence": 0.98,
        }])
        represent.side_effect = ValueError("bad image")
        self.assertEqual(get_face_count("broken.jpg"), 0)
        self.assertEqual(get_face_details("broken.jpg"), [])


if __name__ == "__main__":
    unittest.main()
