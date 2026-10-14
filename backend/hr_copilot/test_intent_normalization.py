#!/usr/bin/env python3
"""Test the intent normalization fix without depending on Ollama."""

import json
import os
import sys
from datetime import datetime

# Add the backend directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Set up Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()

import pytest  # noqa: E402
from hr_copilot.services.intent_normalizer import (  # noqa: E402
    IntentNormalizer,
    intent_normalizer,
)
from hr_copilot.services.pipeline import CopilotError  # noqa: E402


def test_intent_normalization():
    """Test the intent normalization layer that fixes the source mismatch."""

    print("=== INTENT NORMALIZATION TEST ===")
    print(
        "Testing the fix for: 'Intent attendance_update expects source attendance but got employee'"
    )
    print()

    # Simulate problematic LLM output (what Qwen was returning)
    problematic_llm_output = {
        "intent": "attendance_update",
        "source": "employee",  # Wrong source - this was the problem
        "entities": {
            "employee_name": "Akshat Bansal",
            "temporal_expression": "24th September 2026",
            "target_status": "absent",
        },
    }

    original_query = "Make Akshat Bansal as Absent for 24th September 2026"

    print("BEFORE NORMALIZATION:")
    print("LLM Output:", json.dumps(problematic_llm_output, indent=2))
    print()
    print(
        "X This would fail with: Intent 'attendance_update' expects source 'attendance' but got 'employee'"
    )
    print()

    # Apply normalization
    try:
        normalized = intent_normalizer.normalize_intent(
            problematic_llm_output, original_query
        )

        print("AFTER NORMALIZATION:")
        print(
            "Normalized Intent:", json.dumps(normalized, indent=2, default=str)
        )
        print()

        # Verify the fix
        if (
            normalized["intent"] == "attendance_update"
            and normalized["source"] == "attendance"
        ):
            print("SUCCESS: Intent-source mismatch FIXED!")
            print("Intent:", normalized["intent"])
            print(
                "Source:", normalized["source"], "(corrected from 'employee')"
            )
            print("Action type:", normalized["action_type"])
            print("Requires approval:", normalized["requires_approval"])
            print(
                "Target status:", normalized["entities"].get("target_status")
            )
        else:
            print("X Normalization failed")

    except Exception as e:
        print(f"❌ Normalization error: {e}")

    print()
    print("=== TESTING OTHER QUERIES ===")

    # Test other query types
    test_cases = [
        {
            "query": "Who was absent today?",
            "llm_output": {
                "intent": "absence_lookup",
                "source": "attendance",  # Wrong
                "entities": {"temporal_expression": "today"},
            },
            "expected_source": "employee",
        },
        {
            "query": "Show Akshat Bansal's attendance",
            "llm_output": {
                "intent": "attendance_lookup",
                "source": "employee",  # Wrong
                "entities": {"employee_name": "Akshat Bansal"},
            },
            "expected_source": "attendance",
        },
        {
            "query": "Put Rahul on leave tomorrow",
            "llm_output": {
                "intent": "leave_create",
                "source": "attendance",  # Wrong
                "entities": {
                    "employee_name": "Rahul",
                    "temporal_expression": "tomorrow",
                },
            },
            "expected_source": "leave",
        },
    ]

    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case['query']}")
        try:
            normalized = intent_normalizer.normalize_intent(
                test_case["llm_output"], test_case["query"]
            )
            actual_source = normalized["source"]
            expected_source = test_case["expected_source"]

            if actual_source == expected_source:
                print(
                    "  SUCCESS: Source corrected:",
                    test_case["llm_output"]["source"],
                    "->",
                    actual_source,
                )
            else:
                print(
                    "  ERROR: Expected", expected_source, "got", actual_source
                )
        except Exception as e:
            print("  ERROR:", str(e))

    print()
    print("=== NORMALIZATION LAYER DESIGN ===")
    print("1. LLM focuses on semantic understanding only")
    print("2. Backend deterministically maps intent -> source")
    print("3. No more arbitrary source selection by LLM")
    print("4. Status normalization: 'absent' -> 'LEAVE'")
    print(
        "5. Action type classification: write intents -> 'write' + approval required"
    )
    print()
    print("Mapping rules:")
    for intent, source in intent_normalizer.intent_source_mapping.items():
        action_type = (
            "write" if intent in intent_normalizer.write_intents else "read"
        )
        print(f"  {intent} -> {source} ({action_type})")


if __name__ == "__main__":
    test_intent_normalization()


@pytest.mark.parametrize(
    "intent_name",
    [
        "attendance_delete",
        "leave_update",
        "employee_update",
        "bulk_attendance_update",
    ],
)
def test_unsupported_write_intent_is_rejected_before_execution(intent_name):
    with pytest.raises(CopilotError, match="not supported yet"):
        IntentNormalizer().normalize_intent(
            {"intent": intent_name, "entities": {}}
        )


@pytest.mark.parametrize(
    ("phrase", "expected"),
    [
        ("today", "2026-10-14"),
        ("yesterday", "2026-10-13"),
        ("tomorrow", "2026-10-15"),
        ("29th September 2026", "2026-09-29"),
        ("September 29", "2026-09-29"),
        ("29/09/2026", "2026-09-29"),
    ],
)
def test_attendance_date_extraction_handles_supported_calendar_phrasing(
    monkeypatch, phrase, expected
):
    monkeypatch.setattr(
        "django.utils.timezone.localdate",
        lambda: datetime(2026, 10, 14).date(),
    )

    assert IntentNormalizer._extract_attendance_date(phrase) == expected


@pytest.mark.parametrize(
    ("query", "expected_status"),
    [
        ("Mark Asha Rao absent today", "ABSENT"),
        ("Make Asha Rao present yesterday", "PRESENT"),
        ("Set Asha Rao on leave tomorrow", "LEAVE"),
        ("Record attendance for Asha Rao today", "PRESENT"),
    ],
)
def test_attendance_write_inference_preserves_status_identity_and_date(
    monkeypatch, query, expected_status
):
    monkeypatch.setattr(
        "django.utils.timezone.localdate",
        lambda: datetime(2026, 10, 14).date(),
    )

    entities = IntentNormalizer()._infer_attendance_write(query)

    assert entities["target_status"] == expected_status
    assert entities["employee_name"] == "Asha Rao"
    assert entities["date_range"]["start"] == entities["date_range"]["end"]


def test_attendance_write_inference_ignores_reads_and_unrecognized_statuses():
    normalizer = IntentNormalizer()

    assert (
        normalizer._infer_attendance_write("Who was absent yesterday?") is None
    )
    assert (
        normalizer._infer_attendance_write("Mark Asha Rao on vacation today")
        is None
    )
    assert (
        normalizer._infer_attendance_write("Mark Asha Rao present today")[
            "target_status"
        ]
        == "PRESENT"
    )


@pytest.mark.parametrize(
    "query",
    [
        "Mark Asha Rao absent on 2026-02-30",
        "Set Asha Rao present on 31 February 2026",
    ],
)
def test_attendance_write_rejects_impossible_calendar_dates(query):
    with pytest.raises(CopilotError) as raised:
        IntentNormalizer()._infer_attendance_write(query)

    assert raised.value.code == "invalid_date"
