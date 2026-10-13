import io
import json
from urllib.error import URLError

import pytest

from hr_copilot.services import llm, providers
from hr_copilot.services.pipeline import CopilotError


def response_for(content):
    return io.BytesIO(
        json.dumps({"message": {"content": json.dumps(content)}}).encode()
    )


def test_provider_is_optional_when_url_is_not_configured(monkeypatch):
    monkeypatch.delenv("HR_COPILOT_LLM_URL", raising=False)
    monkeypatch.delenv("HR_COPILOT_LLM_PROVIDER", raising=False)
    assert llm.get_structured_intent("How many employees in C1?") is None


def test_ollama_provider_sends_json_intent_request(monkeypatch):
    monkeypatch.setenv("HR_COPILOT_LLM_URL", "http://localhost:11434")
    monkeypatch.setenv("HR_COPILOT_LLM_PROVIDER", "local_ollama_qwen")
    monkeypatch.setenv("HR_COPILOT_LLM_MODEL", "qwen3-8b-q4km-local")
    monkeypatch.setenv("HR_COPILOT_LLM_TIMEOUT_SECONDS", "20")
    calls = []

    def fake_open(request, timeout):
        calls.append((request, timeout))
        return response_for(
            {
                "intent": "employee_count",
                "source": "employee",
                "entities": {"section": "c"},
            }
        )

    monkeypatch.setattr(providers, "_open_local_request", fake_open)
    result = llm.get_structured_intent("How many employees in C?")
    assert result["intent"] == "employee_count"
    assert result["source"] == "employee"
    assert result["entities"] == {"section": "C"}
    assert result["action_type"] == "read"
    assert result["requires_approval"] is False
    request, timeout = calls[0]
    body = json.loads(request.data)
    assert request.full_url == "http://localhost:11434/api/chat"
    assert body["model"] == "qwen3-8b-q4km-local"
    assert body["format"]["required"] == ["intent", "entities"]
    assert timeout == 20
    assert "Return ONLY the required JSON object" in body["messages"][0][
        "content"
    ]


def test_intent_provider_receives_compact_session_and_explicit_context(monkeypatch):
    monkeypatch.setenv("HR_COPILOT_LLM_URL", "http://localhost:11434")
    monkeypatch.setattr(
        llm.session_memory,
        "get_compact_context",
        lambda _session: {"last_department": "Engineering", "employee_id": 8},
    )
    calls = []

    def fake_open(request, timeout):
        calls.append(request)
        return response_for(
            {
                "intent": "employee_lookup",
                "source": "employee",
                "entities": {"employee_id": 8},
            }
        )

    monkeypatch.setattr(providers, "_open_local_request", fake_open)

    result = llm.get_structured_intent(
        "Show that employee", session_id="session-8", context={"section": "C"}
    )

    assert result["entities"]["employee_id"] == 8
    prompt = json.loads(calls[0].data)["messages"][0]["content"]
    assert '"last_department":"Engineering"' in prompt
    assert '"section":"C"' in prompt


def test_non_object_provider_result_returns_safe_invalid_intent(monkeypatch):
    class EmptyProvider:
        def structured_output(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(llm, "get_llm_provider", lambda: EmptyProvider())

    with pytest.raises(CopilotError) as raised:
        llm.get_structured_intent("How many employees?")

    assert raised.value.code == "invalid_intent"
    assert raised.value.status == 503


def test_provider_accepts_absence_intent_as_employee_query(monkeypatch):
    monkeypatch.setenv("HR_COPILOT_LLM_URL", "http://localhost:11434")
    yesterday = "2026-09-23"
    monkeypatch.setattr(
        providers,
        "_open_local_request",
        lambda *_args, **_kwargs: response_for(
            {
                "intent": "absence_lookup",
                "source": "employee",
                "entities": {
                    "date_range": {"start": yesterday, "end": yesterday}
                },
            }
        ),
    )

    result = llm.get_structured_intent("Who was absent yesterday?")
    assert result["intent"] == "absence_lookup"
    assert result["source"] == "employee"
    assert result["entities"] == {
        "date_range": {"start": yesterday, "end": yesterday}
    }


@pytest.mark.parametrize(
    "output",
    [
        {
            "intent": "employee_count",
            "source": "employee",
            "entities": {"sql": "DROP TABLE"},
        },
        {
            "intent": "employee_count",
            "source": "employee",
            "entities": {"date_range": {"start": "yesterday"}},
        },
        {
            "intent": "employee_count",
            "source": "employee",
            "entities": {"employee_type": "CEO"},
        },
        {
            "intent": "employee_count",
            "source": "employee",
            "entities": {"comparison_subsections": [""]},
        },
        {
            "intent": "employee_count",
            "source": "employee",
            "entities": {"is_active": "yes"},
        },
    ],
)
def test_invalid_provider_output_is_rejected(monkeypatch, output):
    monkeypatch.setenv("HR_COPILOT_LLM_URL", "http://localhost:11434")
    monkeypatch.setattr(
        providers,
        "_open_local_request",
        lambda *_args, **_kwargs: response_for(output),
    )
    with pytest.raises(CopilotError):
        llm.get_structured_intent("question")


def test_unsupported_provider_intent_is_normalized_to_unknown(monkeypatch):
    monkeypatch.setenv("HR_COPILOT_LLM_URL", "http://localhost:11434")
    monkeypatch.setattr(
        providers,
        "_open_local_request",
        lambda *_args, **_kwargs: response_for(
            {"intent": "drop_table", "source": "employee", "entities": {}}
        ),
    )

    result = llm.get_structured_intent("run a destructive command")

    assert result["intent"] == "unknown"
    assert result["requires_approval"] is False
    assert result["backend_tool"] is None


def test_provider_supplied_source_is_derived_from_the_intent(monkeypatch):
    monkeypatch.setenv("HR_COPILOT_LLM_URL", "http://localhost:11434")
    monkeypatch.setattr(
        providers,
        "_open_local_request",
        lambda *_args, **_kwargs: response_for(
            {
                "intent": "employee_count",
                "source": "attendance",
                "entities": {},
            }
        ),
    )

    result = llm.get_structured_intent("How many employees?")

    assert result["intent"] == "employee_count"
    assert result["source"] == "employee"


def test_provider_network_failure_returns_controlled_error(monkeypatch):
    monkeypatch.setenv("HR_COPILOT_LLM_URL", "http://localhost:11434")
    monkeypatch.setattr(
        providers,
        "_open_local_request",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("offline")),
    )
    with pytest.raises(CopilotError) as raised:
        llm.get_structured_intent("question")
    assert raised.value.code == "llm_unavailable"
    assert "offline" not in raised.value.message


def test_malformed_provider_json_is_rejected(monkeypatch):
    monkeypatch.setenv("HR_COPILOT_LLM_URL", "http://localhost:11434")
    monkeypatch.setattr(
        providers,
        "_open_local_request",
        lambda *_args, **_kwargs: io.BytesIO(b"not-json"),
    )
    with pytest.raises(CopilotError) as raised:
        llm.get_structured_intent("question")
    assert raised.value.code == "llm_unavailable"


def test_cloud_or_custom_provider_url_is_rejected(monkeypatch):
    monkeypatch.setenv(
        "HR_COPILOT_LLM_URL", "https://llm.example/custom/api/chat"
    )
    with pytest.raises(CopilotError) as raised:
        llm.get_structured_intent("unrelated")
    assert raised.value.code == "llm_unavailable"


def test_follow_up_extraction_whitelists_and_trims_only_requested_values(
    monkeypatch,
):
    class Provider:
        def structured_output(self, messages, *, schema, options):
            assert schema["additionalProperties"] is False
            assert set(schema["properties"]) == {
                "employee_name",
                "employee_email",
                "reason",
            }
            return {
                "employee_name": " Asha Rao ",
                "reason": "  Forgot to check in  ",
                "unexpected": "ignored",
                "employee_email": "   ",
            }

    monkeypatch.setattr(llm, "get_llm_provider", lambda: Provider())

    result = llm.extract_pending_action_fields(
        "Asha Rao forgot to check in", ["employee_name", "reason"]
    )

    assert result == {
        "employee_name": "Asha Rao",
        "reason": "Forgot to check in",
    }


def test_follow_up_extraction_rejects_non_object_provider_result(monkeypatch):
    class Provider:
        def structured_output(self, *args, **kwargs):
            return []

    monkeypatch.setattr(llm, "get_llm_provider", lambda: Provider())

    with pytest.raises(CopilotError) as raised:
        llm.extract_pending_action_fields("reply", ["reason"])

    assert raised.value.code == "invalid_intent"
    assert raised.value.status == 503


@pytest.mark.parametrize(
    ("intent", "data", "expected"),
    [
        (
            {"entities": {"workforce_metric": "shift_assignments"}},
            [{"name": "Asha Rao", "assigned_shift_name": "Morning"}],
            "Asha Rao is assigned to the Morning shift.",
        ),
        (
            {"entities": {"workforce_metric": "shift_assignments"}},
            [{"name": "Asha Rao"}],
            "Asha Rao has no shift assigned.",
        ),
        (
            {"entities": {"attendance_metric": "missing_checkins"}},
            [{}, {}],
            "2 employees have not checked in today.",
        ),
        (
            {"entities": {"attendance_metric": "late_employees"}},
            [{}],
            "1 employee arrived late today.",
        ),
        (
            {"entities": {"attendance_metric": "working_hours"}},
            [{"employee_name": "Asha Rao", "total_working_duration": None}],
            "Working duration is unavailable for the requested range.",
        ),
        (
            {"entities": {"attendance_metric": "incomplete_explanation"}},
            [{}],
            "The attendance record needs review.",
        ),
        (
            {"entities": {"intelligence_metric": "leave_balance"}},
            [{}, {}],
            "Found 2 results for leave balance.",
        ),
        (
            {"source": "attendance"},
            [{"value": 4}],
            "The result is 4.",
        ),
    ],
)
def test_grounded_answers_use_only_the_typed_result(intent, data, expected):
    assert llm.generate_natural_answer("question", intent, data) == expected


@pytest.mark.parametrize(
    ("intent", "data", "expected"),
    [
        (
            {"intent": "attendance_intelligence", "entities": {"attendance_metric": "absence_streaks"}},
            [{}, {}],
            "Found 2 absence streaks of at least two working days.",
        ),
        (
            {"intent": "attendance_intelligence", "entities": {"attendance_metric": "summary"}},
            [{}],
            "Attendance summary returned 1 working-day row.",
        ),
        (
            {"intent": "absence_count"},
            [{"value": 1}],
            "1 employee was absent.",
        ),
        (
            {"intent": "employee_lookup", "source": "employee"},
            [{"first_name": "Asha", "last_name": "Rao", "department": "Engineering"}],
            "Asha Rao is an active employee in Engineering, Section , Subsection .",
        ),
    ],
)
def test_common_deterministic_answers_are_stable(intent, data, expected):
    assert llm._generate_deterministic_answer(intent, data) == expected


def test_answer_fallback_labels_each_supported_result_source():
    assert llm._generate_fallback_answer({"source": "employee"}, [{}]) == (
        "Found 1 employee."
    )
    assert llm._generate_fallback_answer({"source": "attendance"}, [{}, {}]) == (
        "Found 2 attendance records."
    )
    assert llm._generate_fallback_answer({"source": "leave"}, []) == (
        "No matching HR records found."
    )


def test_compact_result_data_keeps_typed_fields_and_applies_row_limits():
    attendance = [
        {
            "first_name": str(index),
            "last_name": "Rao",
            "date": "2026-09-01",
            "status": "PRESENT",
            "private_field": "omit",
        }
        for index in range(12)
    ]

    compacted = llm._compact_result_data(
        attendance, {"source": "attendance"}
    )

    assert len(compacted) == 10
    assert compacted[0] == {
        "first_name": "0",
        "last_name": "Rao",
        "date": "2026-09-01",
        "status": "PRESENT",
    }
    assert llm._compact_result_data([], {"source": "employee"}) == []


@pytest.mark.parametrize(
    "answer",
    ["No matching HR records were found.", "No absent employees were found."],
)
def test_grounding_validator_accepts_supported_empty_result_language(answer):
    llm._validate_grounded_answer(answer, [])


def test_grounding_validator_rejects_unverified_facts():
    with pytest.raises(CopilotError) as raised:
        llm._validate_grounded_answer(
            "Asha Rao received 999 days of leave.",
            [{"first_name": "Asha", "last_name": "Rao", "value": 3}],
        )

    assert raised.value.code == "ungrounded_llm_response"
    assert raised.value.status == 503
