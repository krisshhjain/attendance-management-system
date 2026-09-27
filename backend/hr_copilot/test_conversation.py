from types import SimpleNamespace

from hr_copilot.services import conversation


def test_follow_up_uses_only_structured_employee_context():
    intent = {"intent": "attendance_lookup", "source": "attendance", "entities": {}}
    result = conversation.apply_context("Was she present yesterday?", intent, {"current_employee_id": 9})
    assert result["entities"] == {"employee_id": 9}
    assert intent["entities"] == {}


def test_unrelated_question_does_not_receive_employee_context():
    intent = {"intent": "attendance_lookup", "source": "attendance", "entities": {}}
    result = conversation.apply_context("Show attendance today", intent, {"current_employee_id": 9})
    assert result["entities"] == {}


def test_context_is_saved_without_raw_question_or_response(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        conversation,
        "CopilotConversationContext",
        SimpleNamespace(objects=SimpleNamespace(update_or_create=lambda **kwargs: captured.update(kwargs))),
    )
    conversation.save_context(SimpleNamespace(pk=3), "local-123", {
        "employee": {"employee_id": 9},
        "filters": {"section": "C", "subsection": "C1"},
        "temporal_scope": {"type": "today"},
        "intent": "employee_lookup",
    })
    assert captured["defaults"] == {"context": {
        "current_employee_id": 9,
        "current_section": "C",
        "current_subsection": "C1",
        "current_date_context": {"type": "today"},
        "last_intent": "employee_lookup",
    }}
