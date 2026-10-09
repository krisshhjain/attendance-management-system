"""Regression and adversarial-input tests for user-facing regex paths."""

import time

from django.test import SimpleTestCase

from hr_copilot.services.intent_normalizer import (
    IntentNormalizer,
    _is_find_employee_query,
)
from hr_copilot.services.conversation import apply_context
from hr_copilot.services.pipeline import CopilotError, _apply_deterministic_entities
from hr_copilot.services.regex_safety import (
    find_email_address,
    has_ordered_regex_matches,
)
from hr_copilot.services.semantic_interpreter import SemanticInterpreter


class OrderedRegexMatchingTests(SimpleTestCase):
    def test_email_extraction_preserves_supported_address_shapes(self):
        self.assertEqual(
            find_email_address("Please check Ananya.Jain+hr@example.co.in today"),
            "Ananya.Jain+hr@example.co.in",
        )
        self.assertIsNone(find_email_address("no email address here"))

        identity = IntentNormalizer._extract_workforce_employee_identity(
            "Which shift is assigned to ananya.jain@example.com?"
        )
        self.assertEqual(identity, {"employee_email": "ananya.jain@example.com"})

        entities = {}
        _apply_deterministic_entities(
            "attendance for ananya.jain@example.com", "employee", entities
        )
        self.assertEqual(entities["employee_email"], "ananya.jain@example.com")

        follow_up = apply_context(
            "attendance for new.employee@example.com",
            {"entities": {}},
            {"current_employee_id": 7},
        )
        self.assertNotIn("employee_id", follow_up["entities"])

    def test_email_parser_is_linear_for_long_malformed_addresses(self):
        adversarial = "x@" + ("." * 50_000) + "!"
        started = time.perf_counter()
        self.assertIsNone(find_email_address(adversarial))
        self.assertLess(time.perf_counter() - started, 1.0)

    def test_find_employee_query_preserves_phrase_and_scales_linearly(self):
        self.assertTrue(_is_find_employee_query("find Ananya Jain"))
        self.assertTrue(_is_find_employee_query("Please find Ananya Jain\n"))
        self.assertFalse(_is_find_employee_query("find "))
        self.assertFalse(_is_find_employee_query("find Alice!"))
        inferred = IntentNormalizer._infer_read_intelligence("Find Ananya Jain")
        self.assertEqual(
            inferred,
            ("workforce_intelligence", {"workforce_metric": "employee_search"}),
        )

        adversarial = "find " + ("Ananya " * 20_000) + "!"
        started = time.perf_counter()
        self.assertFalse(_is_find_employee_query(adversarial))
        self.assertLess(time.perf_counter() - started, 1.0)

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
