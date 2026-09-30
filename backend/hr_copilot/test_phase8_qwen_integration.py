"""REAL_QWEN integration tests for the complete interpretation pipeline.

These tests intentionally do not patch get_structured_intent. They call the
configured local Ollama/Qwen provider, then the real parser, normalizer, and
semantic interpreter. They are skipped only when the configured provider is
unavailable.
"""

import json
from datetime import timedelta
from unittest import SkipTest, TestCase

from django.contrib.auth import get_user_model
from django.utils import timezone

from employees.models import Employee
from hr_copilot.services.llm import get_structured_intent
from hr_copilot.services.providers import LLMProviderError, get_llm_provider, provider_health
from hr_copilot.services.semantic_interpreter import semantic_interpreter


class RecordingProvider:
    def __init__(self, provider, records):
        self.provider = provider
        self.records = records

    def structured_output(self, messages, schema="json", options=None):
        content = self.provider.chat(messages, response_format=schema, options=options)
        self.records.append({"messages": messages, "raw_content": content})
        try:
            result = json.loads(content)
        except (TypeError, ValueError) as error:
            raise LLMProviderError("The local Qwen model returned invalid structured output.") from error
        if not isinstance(result, dict):
            raise LLMProviderError("The local Qwen model returned invalid structured output.")
        return result


class REAL_QWEN_IntegrationTests(TestCase):
    """REAL_QWEN tests: raw output -> JSON -> normalizer -> semantic layer."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        health = provider_health()
        if not health.available:
            raise SkipTest(f"REAL_QWEN provider unavailable: {health.detail}")

    def setUp(self):
        User = get_user_model()
        user = User.objects.create_user(
            email=f"real-qwen-krish-{self._testMethodName}@example.test",
            first_name="Krish",
            last_name="Rao",
        )
        self.employee = Employee.objects.create(
            user=user, department="Engineering", employment_type="PERMANENT",
            date_joined=timezone.localdate() - timedelta(days=60), section="C", subsection="C1",
        )
        self.records = []
        self.real_provider = get_llm_provider()

    def run_real_query(self, question):
        """Run the exact real provider path and return diagnostic artifacts."""
        from unittest.mock import patch
        recording = RecordingProvider(self.real_provider, self.records)
        with patch("hr_copilot.services.llm.get_llm_provider", return_value=recording):
            normalized = get_structured_intent(question)
            interpreted = semantic_interpreter.interpret_query(question)
        record = self.records[-1]
        return {
            "query": question,
            "raw_qwen_output": record["raw_content"],
            "parsed_output": json.loads(record["raw_content"]),
            "normalized_intent": normalized,
            "interpreted_intent": interpreted,
        }

    def test_REAL_QWEN_basic_and_domain_queries(self):
        matrix = [
            ("Who has not checked in today?", "attendance_intelligence", "missing_checkins"),
            ("Who was late today?", "attendance_intelligence", "late_employees"),
            ("Show Krish's attendance this month.", "attendance_lookup", None),
            ("How many hours did Krish work today?", "attendance_intelligence", "working_hours"),
            ("What is Krish's leave balance?", "leave_regularization_intelligence", "leave_balance"),
            ("Show pending leave requests.", "leave_regularization_intelligence", "leave_requests"),
            ("Show pending regularization requests.", "leave_regularization_intelligence", "regularization_pending"),
            ("Show Krish's employee details.", "workforce_intelligence", "employee_details"),
            ("What shift is Krish assigned to?", "workforce_intelligence", "shift_assignments"),
        ]
        failures = []
        report = []
        for query, expected_intent, expected_metric in matrix:
            with self.subTest(query=query):
                try:
                    result = self.run_real_query(query)
                except Exception as error:
                    item = {"query": query, "failure_layer": "provider_or_parser", "error": str(error),
                            "expected_intent": expected_intent, "expected_metric": expected_metric,
                            "pass": False}
                    report.append(item)
                    failures.append(item)
                    continue
                actual = result["normalized_intent"]
                metric = actual.get("entities", {}).get("attendance_metric") or actual.get("entities", {}).get("intelligence_metric") or actual.get("entities", {}).get("workforce_metric")
                item = {
                    "query": query, "raw_qwen_output": result["raw_qwen_output"],
                    "parsed_output": result["parsed_output"], "normalized_intent": actual,
                    "expected_intent": expected_intent, "expected_metric": expected_metric,
                    "pass": actual.get("intent") == expected_intent and metric == expected_metric,
                }
                report.append(item)
                if not item["pass"]:
                    failures.append({
                        "query": query, "raw_qwen_output": result["raw_qwen_output"],
                        "parsed_output": result["parsed_output"], "normalized_intent": actual,
                        "expected_intent": expected_intent, "expected_metric": expected_metric,
                        "failure_layer": "normalization_or_intent_selection",
                    })
        print("REAL_QWEN_TRACE\n" + json.dumps(report, indent=2, default=str))
        if failures:
            self.fail("REAL_QWEN failures:\n" + json.dumps(failures, indent=2, default=str))

    def test_REAL_QWEN_read_question_is_not_classified_as_write(self):
        result = self.run_real_query("Who has not checked in today?")
        self.assertEqual(result["normalized_intent"]["action_type"], "read", json.dumps(result, indent=2, default=str))
        self.assertFalse(result["normalized_intent"].get("requires_approval", False))
