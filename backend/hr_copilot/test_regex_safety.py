"""Regression and adversarial-input tests for user-facing regex paths."""

import time

from django.test import SimpleTestCase

from hr_copilot.services.conversation import apply_context
from hr_copilot.services.intent_normalizer import IntentNormalizer
from hr_copilot.services.pipeline import _apply_deterministic_entities
from hr_copilot.services.regex_safety import has_ordered_regex_matches
from hr_copilot.services.semantic_interpreter import SemanticInterpreter
from hr_copilot.services.pipeline import CopilotError


class OrderedRegexMatchingTests(SimpleTestCase):
    def test_ordered_match_preserves_phrase_order_and_line_boundaries(self):
        self.assertTrue(has_ordered_regex_matches("write code in Python", r"\bwrite\b", r"\bpython\b"))
        self.assertFalse(has_ordered_regex_matches("Python, then write", r"\bwrite\b", r"\bpython\b"))
        self.assertFalse(has_ordered_regex_matches("write this\nPython", r"\bwrite\b", r"\bpython\b"))

    def test_long_repeated_security_starters_do_not_backtrack_superlinearly(self):
        adversarial = "write " * 20_000
        started = time.perf_counter()
        SemanticInterpreter()._validate_security(adversarial)
        self.assertLess(time.perf_counter() - started, 1.0)

        with self.assertRaises(CopilotError):
            SemanticInterpreter()._validate_security("Please write code in Python")

    def test_intent_normalizer_handles_repeated_starters_and_keeps_recognition(self):
        adversarial = "compare " * 20_000
        started = time.perf_counter()
        self.assertIsNone(IntentNormalizer._infer_read_intelligence(adversarial))
        self.assertLess(time.perf_counter() - started, 1.0)

        self.assertEqual(
            IntentNormalizer._infer_read_intelligence("Compare attendance week over week")[0],
            "attendance_intelligence",
        )
        self.assertEqual(
            IntentNormalizer._infer_read_intelligence("Show casual leave balance")[0],
            "leave_regularization_intelligence",
        )

    def test_intent_normalizer_shift_phrases_remain_supported(self):
        intent = IntentNormalizer._infer_read_intelligence(
            "Which shift does Ananya work in?"
        )
        self.assertEqual(intent[0], "workforce_intelligence")
        self.assertEqual(intent[1]["employee_name"], "Ananya")

    def test_attendance_name_extraction_handles_adversarial_input(self):
        query = "mark " + ("Ananya " * 20_000) + "nonsense"
        started = time.perf_counter()
        IntentNormalizer._extract_attendance_employee_name(query)
        self.assertLess(time.perf_counter() - started, 1.0)
        self.assertEqual(
            IntentNormalizer._extract_attendance_employee_name("mark Ananya present"),
            "Ananya",
        )

    def test_pipeline_entity_extraction_handles_long_repeated_input(self):
        adversarial = "employee " * 20_000
        entities = {}
        started = time.perf_counter()
        _apply_deterministic_entities(adversarial, "employee", entities)
        self.assertLess(time.perf_counter() - started, 1.0)
        self.assertLess(len(entities.get("employee_name", "")), 100)

    def test_conversation_context_handles_long_repeated_follow_up(self):
        question = "that request " * 20_000
        started = time.perf_counter()
        result = apply_context(
            question,
            {"intent": "leave_lookup", "entities": {}},
            {"current_request_id": "request-123"},
        )
        self.assertLess(time.perf_counter() - started, 1.0)
        self.assertEqual(result["entities"]["request_id"], "request-123")
