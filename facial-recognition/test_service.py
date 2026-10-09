import unittest
import base64
import numpy as np
from PIL import Image
import io
import json
import os
from types import SimpleNamespace
from unittest.mock import patch

# Import the flask app for testing
from app import app
from liveness import LivenessInputError, assess_liveness


class _FakeDetector:
    def __init__(self, faces):
        self.faces = faces

    def setInputSize(self, size):
        self.input_size = size

    def detect(self, image):
        return None, self.faces


class _FakeClassifier:
    def __init__(self, logits):
        self.logits = np.asarray([logits], dtype=np.float32)
        self.feed = None

    def run(self, outputs, feed):
        self.feed = feed
        return [self.logits]

class FRServiceTests(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def _create_dummy_image(self):
        """Creates a dummy base64 white square image (note: RetinaFace will fail to find faces here, but it's for API validation)"""
        img = Image.new('RGB', (100, 100), color='white')
        buffered = io.BytesIO()
        img.save(buffered, format="JPEG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    def test_health_endpoint(self):
        response = self.app.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "ok"})

    def test_non_loopback_api_requests_require_service_token(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FACE_SERVICE_TOKEN", None)
            response = self.app.post(
                "/extract", json={}, environ_base={"REMOTE_ADDR": "192.0.2.10"}
            )
        self.assertEqual(response.status_code, 401)

    def test_configured_service_token_protects_api_but_not_health(self):
        with patch.dict(os.environ, {"FACE_SERVICE_TOKEN": "test-only-token"}):
            missing_token = self.app.post("/extract", json={})
            valid_token = self.app.post(
                "/extract", json={}, headers={"Authorization": "Bearer test-only-token"}
            )
            health = self.app.get("/health")
        self.assertEqual(missing_token.status_code, 401)
        self.assertEqual(valid_token.status_code, 400)
        self.assertEqual(health.status_code, 200)

    def test_server_defaults_to_loopback_and_guards_non_loopback_bind(self):
        from app import _configured_bind_host

        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_configured_bind_host(), "127.0.0.1")
            os.environ["FR_BIND_HOST"] = "0.0.0.0"
            with self.assertRaisesRegex(RuntimeError, "FACE_SERVICE_TOKEN"):
                _configured_bind_host()
            os.environ["FACE_SERVICE_TOKEN"] = "test-only-token"
            self.assertEqual(_configured_bind_host(), "0.0.0.0")

    def test_recognize_missing_fields(self):
        response = self.app.post('/recognize', json={"image": "dummy"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json)

    def test_recognize_no_face(self):
        # Using a dummy white image, no faces will be detected
        dummy_b64 = self._create_dummy_image()
        response = self.app.post('/recognize', json={
            "image": dummy_b64,
            "candidates": [{"id": 1, "template": [0.1]*512}]
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json)

    @patch('app.assess_liveness', return_value=type('Result', (), {
        'is_live': True, 'reason': 'live'
    })())
    @patch('app.extract_primary_face_embedding', return_value=np.array([1.0] + [0.0] * 511))
    def test_live_passes_and_normal_recognition_contract_is_preserved(self, extract, assess):
        response = self.app.post('/recognize', json={
            "image": self._create_detailed_image(),
            "candidates": [{"id": 7, "template": [1.0] + [0.0] * 511}],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "match")
        self.assertEqual(response.json["employee_id"], 7)
        self.assertIn("distance", response.json)
        extract.assert_called_once()
        assess.assert_called_once()

    @patch('app.assess_liveness', return_value=type('Result', (), {
        'is_live': False, 'reason': 'spoof-detected'
    })())
    @patch('app.extract_primary_face_embedding')
    def test_spoof_input_fails_predictably(self, extract, assess):
        response = self.app.post('/recognize', json={
            "image": self._create_spoof_like_image(),
            "candidates": [{"id": 7, "template": [1.0] + [0.0] * 511}],
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {
            "status": "liveness_failed",
            "reason": "spoof-detected",
        })
        extract.assert_not_called()

    @patch('app.assess_liveness', side_effect=__import__('liveness').LivenessInputError('Ambiguous multi-face image'))
    @patch('app.extract_primary_face_embedding')
    def test_multi_face_response_remains_a_400_error(self, extract, assess):
        response = self.app.post('/recognize', json={
            "image": self._create_detailed_image(),
            "candidates": [{"id": 7, "template": [1.0] + [0.0] * 511}],
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("multi-face", response.json["error"].lower())
        extract.assert_not_called()

    @patch('app.assess_liveness', return_value=type('Result', (), {
        'is_live': True, 'reason': 'live'
    })())
    @patch('app.extract_primary_face_embedding', return_value=np.array([1.0] + [0.0] * 511))
    def test_unknown_response_contract_is_preserved(self, extract, assess):
        response = self.app.post('/recognize', json={
            "image": self._create_detailed_image(),
            "candidates": [{"id": 7, "template": [0.0, 1.0] + [0.0] * 510}],
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "unknown")
        self.assertIn("distance", response.json)

    @patch('app.extract_primary_face_embedding')
    @patch('app.assess_liveness', side_effect=RuntimeError('model unavailable'))
    def test_liveness_error_fails_safely(self, assess, extract):
        response = self.app.post('/recognize', json={
            "image": self._create_detailed_image(),
            "candidates": [{"id": 7, "template": [1.0] + [0.0] * 511}],
        })
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json, {
            "status": "liveness_error",
            "error": "Liveness assessment failed",
        })
        extract.assert_not_called()

    def _sequence_payload(self, frame_count=5):
        return {
            "frames": [self._create_sequence_image(index) for index in range(frame_count)],
            "captured_at_ms": [index * 300 for index in range(frame_count)],
            "candidates": [{"id": 7, "template": [1.0] + [0.0] * 511}],
        }

    @staticmethod
    def _create_sequence_image(index):
        image = np.zeros((160, 160, 3), dtype=np.uint8)
        for y in range(160):
            for x in range(160):
                image[y, x] = [(x * 3 + index) % 256, (y * 5 + index * 2) % 256, (x + y + index * 3) % 256]
        pil = Image.fromarray(image, 'RGB')
        buffered = io.BytesIO()
        pil.save(buffered, format='JPEG')
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    @patch('app.assess_liveness')
    @patch('app.extract_primary_face_embedding', return_value=np.array([1.0] + [0.0] * 511))
    def test_recognize_sequence_all_live_keeps_match_contract(self, extract, assess):
        assess.side_effect = [SimpleNamespace(is_live=True, reason='live', real_score=2.0)] * 5
        response = self.app.post('/recognize-sequence', json=self._sequence_payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['status'], 'match')
        self.assertEqual(response.json['employee_id'], 7)
        self.assertIn('distance', response.json)
        self.assertEqual(assess.call_count, 5)
        extract.assert_called_once()

    @patch('app.assess_liveness')
    @patch('app.extract_primary_face_embedding')
    def test_recognize_sequence_inconsistent_frames_fail_quorum(self, extract, assess):
        assess.side_effect = [
            SimpleNamespace(is_live=True, reason='live', real_score=1.0),
            SimpleNamespace(is_live=False, reason='spoof-detected', real_score=-1.0),
            SimpleNamespace(is_live=True, reason='live', real_score=1.0),
            SimpleNamespace(is_live=False, reason='spoof-detected', real_score=-1.0),
            SimpleNamespace(is_live=True, reason='live', real_score=1.0),
        ]
        response = self.app.post('/recognize-sequence', json=self._sequence_payload())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['status'], 'liveness_failed')
        self.assertEqual(response.json['reason'], 'sequence-inconsistent')
        extract.assert_not_called()

    @patch('app.assess_liveness', return_value=SimpleNamespace(is_live=True, reason='live', real_score=1.0))
    @patch('app.extract_primary_face_embedding')
    def test_recognize_sequence_one_positive_cannot_override_repeated_negative(self, extract, assess):
        assess.side_effect = [
            SimpleNamespace(is_live=True, reason='live', real_score=1.0),
            SimpleNamespace(is_live=False, reason='spoof-detected', real_score=-1.0),
            SimpleNamespace(is_live=False, reason='spoof-detected', real_score=-1.0),
            SimpleNamespace(is_live=False, reason='spoof-detected', real_score=-1.0),
            SimpleNamespace(is_live=False, reason='spoof-detected', real_score=-1.0),
        ]
        response = self.app.post('/recognize-sequence', json=self._sequence_payload())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['status'], 'liveness_failed')
        extract.assert_not_called()

    @patch('app.assess_liveness', return_value=SimpleNamespace(is_live=True, reason='live', real_score=1.0))
    @patch('app.extract_primary_face_embedding')
    def test_recognize_sequence_repeated_identical_frames_do_not_count_as_evidence(self, extract, assess):
        payload = self._sequence_payload()
        payload['frames'] = [payload['frames'][0]] * 5
        response = self.app.post('/recognize-sequence', json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['status'], 'liveness_failed')
        self.assertEqual(response.json['reason'], 'sequence-inconsistent')
        assess.assert_called_once()
        extract.assert_not_called()

    @patch('app.assess_liveness', return_value=SimpleNamespace(is_live=False, reason='spoof-detected', real_score=-1.0))
    @patch('app.extract_primary_face_embedding')
    def test_recognize_sequence_spoof_rejected(self, extract, assess):
        response = self.app.post('/recognize-sequence', json=self._sequence_payload())
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['status'], 'liveness_failed')
        self.assertEqual(response.json['reason'], 'spoof-detected')
        extract.assert_not_called()

    def test_recognize_sequence_missing_or_insufficient_frames_rejected(self):
        missing = self.app.post('/recognize-sequence', json={"candidates": []})
        short = self.app.post('/recognize-sequence', json=self._sequence_payload(frame_count=2))
        self.assertEqual(missing.status_code, 400)
        self.assertEqual(short.status_code, 400)
        self.assertEqual(short.json['status'], 'liveness_failed')
        self.assertEqual(short.json['reason'], 'insufficient-frames')

    def test_recognize_sequence_malformed_frame_timing_rejected(self):
        payload = self._sequence_payload()
        payload['captured_at_ms'] = [0, 10, 20, 30, 40]
        response = self.app.post('/recognize-sequence', json=payload)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json['reason'], 'invalid-frame-timing')

    @patch('app.assess_liveness', side_effect=RuntimeError('model unavailable'))
    @patch('app.extract_primary_face_embedding')
    def test_recognize_sequence_liveness_runtime_error_fails_closed(self, extract, assess):
        response = self.app.post('/recognize-sequence', json=self._sequence_payload())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json['status'], 'liveness_error')
        extract.assert_not_called()

    @patch('app.assess_liveness', return_value=SimpleNamespace(is_live=True, reason='live', real_score=2.25))
    @patch('app.extract_primary_face_embedding', return_value=np.array([1.0] + [0.0] * 511))
    def test_recognize_sequence_diagnostics_are_metadata_only_and_opt_in(self, extract, assess):
        app.config['LIVENESS_DIAGNOSTICS_ENABLED'] = True
        try:
            payload = self._sequence_payload()
            payload.update({"test_case": "phone-screen-photo", "device": "test-phone", "attendance_event_created": False})
            response = self.app.post('/recognize-sequence', json=payload)
        finally:
            app.config['LIVENESS_DIAGNOSTICS_ENABLED'] = False
        diagnostics = response.json['diagnostics']
        self.assertEqual(diagnostics['frame_count'], 5)
        self.assertEqual(len(diagnostics['frames']), 5)
        self.assertEqual(diagnostics['final_liveness'], 'passed')
        self.assertEqual(diagnostics['recognition_result'], 'match')
        self.assertEqual(diagnostics['test_case'], 'phone-screen-photo')
        self.assertEqual(diagnostics['device'], 'test-phone')
        self.assertFalse(diagnostics['attendance_event_created'])
        self.assertGreaterEqual(diagnostics['total_latency_ms'], 0)
        self.assertTrue(all('real_score' in frame for frame in diagnostics['frames']))
        self.assertNotIn('image', diagnostics)

    @staticmethod
    def _create_detailed_image():
        image = np.zeros((160, 160, 3), dtype=np.uint8)
        for y in range(160):
            for x in range(160):
                image[y, x] = [(x * 3) % 256, (y * 5) % 256, (x + y) % 256]
        pil = Image.fromarray(image, 'RGB')
        buffered = io.BytesIO()
        pil.save(buffered, format='JPEG')
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    @staticmethod
    def _create_spoof_like_image():
        image = np.full((160, 160, 3), (128, 128, 128), dtype=np.uint8)
        image[35:125, 45:115] = (145, 145, 145)
        pil = Image.fromarray(image, 'RGB')
        buffered = io.BytesIO()
        pil.save(buffered, format='JPEG')
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    @staticmethod
    def _fake_face(x=20, y=20, width=60, height=60):
        return np.array([x, y, width, height] + [0.0] * 10 + [0.99], dtype=np.float32)

    @patch('liveness._load_runtime')
    def test_minifas_real_class_and_128_rgb_tensor(self, load_runtime):
        detector = _FakeDetector(np.array([self._fake_face()]))
        classifier = _FakeClassifier([3.0, 1.0])
        load_runtime.return_value = (detector, classifier, 'input')
        result = assess_liveness(np.full((100, 100, 3), 120, dtype=np.uint8))
        self.assertTrue(result.is_live)
        self.assertAlmostEqual(result.real_score, 2.0)
        tensor = classifier.feed['input']
        self.assertEqual(tensor.shape, (1, 3, 128, 128))
        self.assertEqual(tensor.dtype, np.float32)

    @patch('liveness._load_runtime')
    def test_minifas_spoof_class_is_rejected(self, load_runtime):
        detector = _FakeDetector(np.array([self._fake_face()]))
        classifier = _FakeClassifier([1.0, 3.0])
        load_runtime.return_value = (detector, classifier, 'input')
        result = assess_liveness(np.full((100, 100, 3), 120, dtype=np.uint8))
        self.assertFalse(result.is_live)
        self.assertEqual(result.reason, 'spoof-detected')

    @patch('liveness._load_runtime')
    def test_liveness_detector_no_face_fails_closed_with_legacy_error(self, load_runtime):
        load_runtime.return_value = (_FakeDetector(None), _FakeClassifier([3.0, 1.0]), 'input')
        with self.assertRaisesRegex(LivenessInputError, 'No faces detected'):
            assess_liveness(np.zeros((100, 100, 3), dtype=np.uint8))

    @patch('liveness._load_runtime')
    def test_liveness_detector_rejects_ambiguous_multi_face(self, load_runtime):
        faces = np.array([self._fake_face(5, 10), self._fake_face(35, 10)])
        load_runtime.return_value = (_FakeDetector(faces), _FakeClassifier([3.0, 1.0]), 'input')
        with self.assertRaisesRegex(LivenessInputError, 'multi-face'):
            assess_liveness(np.zeros((100, 100, 3), dtype=np.uint8))

if __name__ == '__main__':
    unittest.main()
