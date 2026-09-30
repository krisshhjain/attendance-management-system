from types import SimpleNamespace

from hr_copilot.services import conversation
from hr_copilot.services.session_memory import SessionMemoryManager
from hr_copilot.services import session_memory


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


def test_compact_session_context_does_not_send_raw_previous_question(monkeypatch):
    manager = SessionMemoryManager()
    monkeypatch.setattr(session_memory.cache, "get", lambda *_args: {
        "last_intent": "attendance_lookup",
        "employee_name": "Asha Rao",
        "last_query": "Show Asha's attendance for last month",
        "context_count": 2,
    })

    assert manager.get_compact_context("conversation-a") == {
        "last_intent": "attendance_lookup",
        "employee_name": "Asha Rao",
    }


def test_follow_up_inherits_employee_and_full_date_range():
    intent = {"intent": "attendance_intelligence", "source": "attendance", "entities": {"attendance_metric": "working_hours"}}
    result = conversation.apply_context(
        "How many hours did he work?", intent,
        {
            "current_employee_id": 9,
            "current_date": "2026-09-01",
            "current_date_end": "2026-09-30",
            "last_intent": "attendance_intelligence",
        },
    )
    assert result["entities"]["employee_id"] == 9
    assert result["entities"]["date_range"] == {"start": "2026-09-01", "end": "2026-09-30"}


def test_relative_date_and_leave_request_reference_are_resolved():
    intent = {"intent": "leave_approve", "source": "leave", "entities": {}}
    result = conversation.apply_context(
        "Approve that leave request for yesterday", intent,
        {"current_employee_id": 9, "current_request_id": 41},
    )
    assert result["entities"] == {"employee_id": 9, "request_id": 41}


def test_context_reset_removes_follow_up_facts(monkeypatch):
    manager = SessionMemoryManager()
    deleted = []
    monkeypatch.setattr(session_memory.cache, "delete", lambda key: deleted.append(key))
    manager.clear_session("conversation-reset")
    assert deleted == ["hr_copilot_session:conversation-reset"]
