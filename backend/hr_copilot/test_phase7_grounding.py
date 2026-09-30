from django.test import SimpleTestCase

from hr_copilot.services.llm import generate_natural_answer
from hr_copilot.services.response_schema import safe_error_message


class Phase7GroundingTests(SimpleTestCase):
    def test_empty_results_are_explicit(self):
        answer = generate_natural_answer("show attendance", {"intent": "attendance_lookup", "source": "attendance", "entities": {}}, [])
        self.assertEqual(answer, "No matching HR records were found.")

    def test_numeric_answer_comes_from_structured_value(self):
        answer = generate_natural_answer(
            "how many employees", {"intent": "employee_count", "source": "employee", "entities": {}},
            [{"value": 17}],
        )
        self.assertEqual(answer, "The result is 17.")
        self.assertNotIn("18", answer)

    def test_typed_metric_answer_uses_only_result_rows(self):
        answer = generate_natural_answer(
            "how many hours", {"intent": "attendance_intelligence", "entities": {"attendance_metric": "working_hours"}},
            [{"employee_name": "Asha Rao", "total_working_duration": "08:00:00"}],
        )
        self.assertEqual(answer, "Asha Rao worked 08:00:00 in the requested range.")

    def test_provider_failure_messages_do_not_expose_internals(self):
        self.assertEqual(
            safe_error_message("llm_unavailable", "local Qwen URL http://internal:11434 failed"),
            "I couldn't interpret that request right now. Please try again.",
        )
        self.assertNotIn("Qwen", safe_error_message("llm_unavailable", "Qwen error"))
