import json
from types import SimpleNamespace

import pytest

from hr_copilot.services import llm
from hr_copilot.services.conversation import apply_context, save_context
from hr_copilot.services.pipeline import (
    CopilotError,
    analyze_question,
    build_sql,
    derive_scope,
    plan_query,
    validate_sql,
)


class FakeProvider:
    def __init__(self, answer):
        self.answer = answer
        self.messages = None

    def structured_output(self, messages, *, schema, options=None):
        self.messages = messages
        assert schema == llm.FINAL_ANSWER_SCHEMA
        assert options == {"num_predict": 96}
        return {"answer": self.answer}


def use_provider(monkeypatch, answer):
    provider = FakeProvider(answer)
    monkeypatch.setattr(llm, "get_llm_provider", lambda: provider)
    return provider


def test_1_successful_attendance_result_natural_response(monkeypatch):
    provider = use_provider(monkeypatch, "Asha Rao was PRESENT on 2026-09-25.")
    data = [{"first_name": "Asha", "last_name": "Rao", "date": "2026-09-25", "status": "PRESENT"}]
    assert llm.generate_natural_answer("Was Asha present?", {"intent": "attendance_lookup"}, data) == provider.answer
    assert json.dumps(data) in provider.messages[1]["content"]


def test_2_empty_result_truthful_no_record_response(monkeypatch):
    use_provider(monkeypatch, "No matching HR records were found.")
    assert llm.generate_natural_answer("Show attendance", {"intent": "attendance_lookup"}, []) == "No matching HR records were found."


def test_3_employee_profile_result_natural_response(monkeypatch):
    answer = "Asha Rao is an active permanent employee in Engineering, Section C, Subsection C1."
    use_provider(monkeypatch, answer)
    data = [{"name": "Asha Rao", "department": "Engineering", "employment_type": "PERMANENT", "section": "C", "subsection": "C1", "is_active": True}]
    assert llm.generate_natural_answer("Tell me about Asha", {"intent": "employee_lookup"}, data) == answer


def test_4_multiple_attendance_records_useful_summary(monkeypatch):
    use_provider(monkeypatch, "2 attendance records were found: Asha Rao and Ravi Shah.")
    data = [{"name": "Asha Rao"}, {"name": "Ravi Shah"}]
    assert llm.generate_natural_answer("Who attended?", {"intent": "attendance_lookup"}, data).startswith("2 attendance")


def test_5_backend_error_no_fabricated_answer(monkeypatch):
    monkeypatch.setattr(llm, "get_llm_provider", lambda: FakeProvider(""))
    with pytest.raises(CopilotError) as raised:
        llm.generate_natural_answer("Show attendance", {"intent": "attendance_lookup"}, [{"value": 1}])
    assert raised.value.code == "invalid_llm_response"


def test_6_unverified_factual_additions_are_rejected(monkeypatch):
    use_provider(monkeypatch, "Asha Rao was PRESENT on 2026-09-26 with employee ID 999.")
    data = [{"first_name": "Asha", "last_name": "Rao", "date": "2026-09-26", "status": "PRESENT"}]
    with pytest.raises(CopilotError) as raised:
        llm.generate_natural_answer("Was Asha present?", {"intent": "attendance_lookup"}, data)
    assert raised.value.code == "ungrounded_llm_response"


def test_7_existing_authorization_remains_enforced():
    user = SimpleNamespace(is_superuser=False, is_system_admin=True, hr_copilot_sections=["A"], hr_copilot_subsections=None)
    scope = derive_scope(user)
    intent = {"intent": "attendance_lookup", "source": "attendance", "entities": {"section": "C"}}
    with pytest.raises(CopilotError) as raised:
        plan_query(intent, scope)
    assert raised.value.code == "scope_denied"
    assert raised.value.status == 403


def test_8_existing_sql_safety_remains_enforced():
    sql = "DELETE FROM employees_employee"
    with pytest.raises(CopilotError) as raised:
        validate_sql(sql)
    assert raised.value.code == "sql_rejected"


def test_9_existing_conversation_followups_remain_functional():
    intent = {"intent": "attendance_lookup", "source": "attendance", "entities": {}}
    updated_intent = apply_context("Was she present yesterday?", intent, {"current_employee_id": 9, "current_section": "C"})
    assert updated_intent["entities"].get("employee_id") == 9
