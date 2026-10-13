from datetime import date, timedelta
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import ManagerScope
from hr_copilot import views
from hr_copilot.services import (conversation, pipeline,
                                 write_actions as write_action_module,
                                 write_executor as write_executor_module)
from hr_copilot.services.pipeline import CopilotError
from hr_copilot.services.write_actions import write_action_planner
from hr_copilot.services.write_executor import write_action_executor


class FakeAudit:
    def __init__(self, **values):
        self.pk = 101
        self.id = self.pk
        self.validation_result = "not_run"
        self.scope_result = "not_run"
        self.execution_result = "not_run"
        self.error_code = ""
        self.sql = ""
        self.__dict__.update(values)
        self.saved_updates = []

    def save(self, update_fields=None):
        self.saved_updates.append(update_fields)


class FakeLeaveTypes(list):
    def distinct(self):
        return self


@pytest.fixture
def api(monkeypatch):
    factory = APIRequestFactory()
    audit_records = []

    def create_audit(**values):
        audit = FakeAudit(**values)
        audit_records.append(audit)
        return audit

    monkeypatch.setattr(
        views,
        "CopilotQueryAudit",
        SimpleNamespace(objects=SimpleNamespace(create=create_audit)),
    )
    # These API tests use a lightweight user double rather than a database-backed
    # User instance. Conversation persistence is covered by the database tests.
    monkeypatch.setattr(views, "append_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(views, "load_context", lambda *args, **kwargs: {})
    monkeypatch.setattr(views, "save_context", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        views.pending_action_manager, "get_awaiting_action", lambda *args: None
    )
    monkeypatch.setattr(
        views.pending_action_manager, "get_session_actions", lambda *args: {}
    )
    monkeypatch.setattr(
        views.pending_action_manager, "get_user_actions", lambda *args: {}
    )

    # These request tests exercise API planning and authorization, not the live
    # Ollama integration. Keep the provider behind its separate integration
    # tests and supply deterministic intents here.
    def analyze_test_question(question, *args, **kwargs):
        lower = question.casefold()
        if "absent yesterday" in lower:
            yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
            return {
                "intent": "absence_lookup",
                "source": "employee",
                "action_type": "read",
                "entities": {
                    "date_range": {"start": yesterday, "end": yesterday}
                },
            }

        if "section d" in lower:
            intent, source = "attendance_lookup", "attendance"
            entities = {"section": "D"}
        else:
            subsection = "C2" if "c2" in lower else "C1"
            intent, source = "employee_count", "employee"
            entities = {"section": "C", "subsection": subsection}

        return {
            "intent": intent,
            "source": source,
            "action_type": "read",
            "entities": entities,
        }

    monkeypatch.setattr(views, "analyze_question", analyze_test_question)

    def manager_scope_records(manager, is_active):
        assert is_active is True
        return [
            SimpleNamespace(scope_type=ManagerScope.SECTION, value=section)
            for section in manager.hr_copilot_sections
        ]

    monkeypatch.setattr(
        ManagerScope.objects, "filter", manager_scope_records
    )
    return factory, audit_records


def system_admin(**overrides):
    values = {
        "id": 1,
        "is_authenticated": True,
        "is_active": True,
        "is_system_admin": True,
        "is_superuser": False,
        "hr_copilot_sections": ["C"],
        "hr_copilot_subsections": ["C1", "C2"],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def call_endpoint(factory, user=None, payload=None):
    request = factory.post(
        "/api/hr-copilot/query/", payload or {}, format="json"
    )
    if user is not None:
        force_authenticate(request, user=user)
    return views.HRCopilotQueryView.as_view()(request)


def call_action_endpoint(factory, user=None, payload=None):
    request = factory.post(
        "/api/hr-copilot/actions/approve/", payload or {}, format="json"
    )
    if user is not None:
        force_authenticate(request, user=user)
    return views.HRCopilotActionApprovalView.as_view()(request)


def test_query_requires_authentication(api):
    factory, audit_records = api
    response = call_endpoint(factory)
    assert response.status_code == 401
    assert audit_records == []


def test_query_requires_system_admin(api):
    factory, audit_records = api
    employee = system_admin(is_system_admin=False)
    response = call_endpoint(
        factory, employee, {"message": "How many employees?"}
    )
    assert response.status_code == 403
    assert response.data["detail"] == "System Admin access is required."
    assert audit_records == []


@pytest.mark.parametrize("message", [None, "", "   ", "x" * 2001, []])
def test_query_rejects_invalid_or_oversized_message_before_auditing(api, message):
    factory, audit_records = api

    response = call_endpoint(
        factory,
        system_admin(),
        {"message": message, "conversation_id": "invalid-query"},
    )

    assert response.status_code == 400
    assert response.data["detail"] == "Enter a question of up to 2,000 characters."
    assert audit_records == []


@pytest.mark.parametrize("conversation_id", [" ", "x" * 129, ["conversation"]])
def test_query_rejects_invalid_conversation_id_before_auditing(api, conversation_id):
    factory, audit_records = api

    response = call_endpoint(
        factory,
        system_admin(),
        {"message": "How many employees?", "conversation_id": conversation_id},
    )

    assert response.status_code == 400
    assert response.data["detail"].startswith("conversation_id must be")
    assert audit_records == []


def test_health_endpoint_blocks_non_admins_before_provider_access(api, monkeypatch):
    factory, _ = api
    monkeypatch.setattr(
        views, "provider_health", lambda: pytest.fail("Unauthorized health request reached provider"),
    )
    request = factory.get("/api/hr-copilot/health/")
    force_authenticate(request, user=system_admin(is_system_admin=False))

    response = views.HRCopilotHealthView.as_view()(request)

    assert response.status_code == 403
    assert response.data["detail"] == "System Admin access is required."


def test_conversation_endpoint_blocks_non_admins_before_loading_history(api, monkeypatch):
    factory, _ = api
    monkeypatch.setattr(
        views, "load_messages", lambda *_: pytest.fail("Unauthorized conversation read")
    )
    request = factory.get("/api/hr-copilot/conversations/conversation-123/")
    force_authenticate(request, user=system_admin(is_system_admin=False))

    response = views.HRCopilotConversationView.as_view()(request, "conversation-123")

    assert response.status_code == 403
    assert response.data["detail"] == "System Admin access is required."


def test_admin_can_read_only_the_requested_conversation(api, monkeypatch):
    factory, _ = api
    history = [{"role": "user", "content": "Show Section C attendance"}]
    loaded = []
    monkeypatch.setattr(
        views,
        "load_messages",
        lambda user, conversation: loaded.append((user.id, conversation)) or history,
    )
    request = factory.get("/api/hr-copilot/conversations/chat-c-17/")
    force_authenticate(request, user=system_admin())

    response = views.HRCopilotConversationView.as_view()(request, "chat-c-17")

    assert response.status_code == 200
    assert response.data == {"conversation_id": "chat-c-17", "messages": history}
    assert loaded == [(1, "chat-c-17")]


def test_cancel_awaiting_action_returns_its_action_id(api, monkeypatch):
    factory, _ = api
    action = {"action_id": "pending-action-123", "intent": {}}
    monkeypatch.setattr(
        views.pending_action_manager,
        "get_awaiting_action",
        lambda *args: action,
    )
    monkeypatch.setattr(
        views.pending_action_manager,
        "cancel_action",
        lambda *args: action,
    )
    monkeypatch.setattr(views, "record_event", lambda **kwargs: None)
    monkeypatch.setattr(
        views, "_record_copilot_action_event", lambda **kwargs: None
    )
    monkeypatch.setattr(views, "update_action_message", lambda *args: None)

    response = call_endpoint(
        factory,
        system_admin(),
        {"message": "cancel", "conversation_id": "cancel-test"},
    )

    assert response.status_code == 200
    assert response.data["action_id"] == action["action_id"]


def test_query_confirmation_executes_action_for_matching_conversation(api, monkeypatch):
    factory, _ = api
    conversation_id = "confirm-this-conversation"
    pending = {
        "action_id": "confirmed-action-1",
        "intent": "attendance_create",
        "conversation_id": conversation_id,
    }
    approved = {**pending, "status": "APPROVED"}
    result = {
        "success": True,
        "operation": "created",
        "message": "Attendance created.",
    }
    executed = []
    events = []
    monkeypatch.setattr(views, "record_event", lambda **_: None)
    monkeypatch.setattr(
        views.pending_action_manager,
        "get_session_actions",
        lambda *_: {pending["action_id"]: pending},
    )
    monkeypatch.setattr(
        views.pending_action_manager, "approve_action", lambda *_: approved
    )
    monkeypatch.setattr(
        views.write_action_executor,
        "execute_approved_action",
        lambda _action, _user: result,
    )
    monkeypatch.setattr(
        views.pending_action_manager,
        "mark_executed",
        lambda *args: executed.append(args),
    )
    monkeypatch.setattr(
        views, "_record_copilot_action_event", lambda **kwargs: events.append(kwargs)
    )
    monkeypatch.setattr(views, "update_action_message", lambda *args: None)

    response = call_endpoint(
        factory,
        system_admin(),
        {"message": "confirm", "conversation_id": conversation_id},
    )

    assert response.status_code == 200
    assert response.data["query_status"] == "executed"
    assert response.data["action_result"] == result
    assert len(executed) == 1
    assert events[0]["event_type"] == "COPILOT_ACTION_CONFIRMED"


@pytest.mark.parametrize(
    "payload",
    [
        {"action_id": "a", "action": "approve"},
        {"action_id": "a", "action": "approve", "conversation_id": " "},
        {
            "action_id": "a",
            "action": "approve",
            "conversation_id": "x" * 129,
        },
        {"action": "approve", "conversation_id": "conversation"},
        {"action_id": "a", "conversation_id": "conversation"},
        {
            "action_id": "a",
            "action": "execute",
            "conversation_id": "conversation",
        },
    ],
)
def test_action_approval_rejects_invalid_request_fields(api, payload):
    factory, _ = api

    response = call_action_endpoint(factory, system_admin(), payload)

    assert response.status_code == 400
    assert "detail" in response.data


def test_action_approval_requires_system_admin(api):
    factory, _ = api

    response = call_action_endpoint(
        factory,
        system_admin(is_system_admin=False),
        {
            "action_id": "a",
            "action": "approve",
            "conversation_id": "conversation",
        },
    )

    assert response.status_code == 403
    assert response.data["detail"] == "System Admin access is required."


def test_action_approval_executes_and_returns_confirmed_result(api, monkeypatch):
    factory, _ = api
    action = {
        "action_id": "action-123",
        "intent": "employee_status_update",
        "description": "Deactivate Asha Rao",
        "conversation_id": "conversation-123",
    }
    result = {"success": True, "message": "Employee deactivated."}
    events = []
    monkeypatch.setattr(
        views.pending_action_manager,
        "approve_action",
        lambda *args: action,
    )
    monkeypatch.setattr(
        views.write_action_executor,
        "execute_approved_action",
        lambda pending, user: result,
    )
    monkeypatch.setattr(
        views.pending_action_manager,
        "mark_executed",
        lambda *args: events.append(("executed", args)),
    )
    monkeypatch.setattr(
        views, "_record_copilot_action_event", lambda **kw: events.append(kw)
    )
    monkeypatch.setattr(views, "update_action_message", lambda *args: None)
    monkeypatch.setattr(views, "append_message", lambda *args: None)
    monkeypatch.setattr(
        "hr_copilot.services.llm.generate_natural_answer",
        lambda *args, **kwargs: "Completed.",
    )

    response = call_action_endpoint(
        factory,
        system_admin(),
        {
            "action_id": action["action_id"],
            "action": "approve",
            "conversation_id": "conversation-123",
        },
    )

    assert response.status_code == 200
    assert response.data["response_type"] == "action_success"
    assert response.data["query_status"] == "executed"
    assert response.data["action_result"] == result
    assert any(
        event.get("event_type") == "COPILOT_ACTION_CONFIRMED"
        for event in events
        if isinstance(event, dict)
    )


def test_action_approval_reports_copilot_error_without_success(api, monkeypatch):
    factory, _ = api
    monkeypatch.setattr(
        views.pending_action_manager,
        "approve_action",
        lambda *args: (_ for _ in ()).throw(
            CopilotError("scope_denied", "Authorization scope has changed", 403)
        ),
    )
    failed = []
    monkeypatch.setattr(
        views.pending_action_manager,
        "mark_failed",
        lambda *args: failed.append(args),
    )
    monkeypatch.setattr(
        views.HRCopilotActionApprovalView,
        "_record_failure",
        staticmethod(lambda *args: None),
    )

    response = call_action_endpoint(
        factory,
        system_admin(),
        {
            "action_id": "action-123",
            "action": "approve",
            "conversation_id": "conversation-123",
        },
    )

    assert response.status_code == 403
    assert response.data["query_status"] == "failed"
    assert response.data["code"] == "scope_denied"
    assert len(failed) == 1


def test_action_cancellation_does_not_execute_product_changes(api, monkeypatch):
    factory, _ = api
    action = {
        "action_id": "action-cancel-123",
        "intent": "attendance_update",
        "conversation_id": "conversation-123",
    }
    events = []
    monkeypatch.setattr(
        views.pending_action_manager,
        "cancel_action",
        lambda *args: action,
    )
    monkeypatch.setattr(
        views.write_action_executor,
        "execute_approved_action",
        lambda *_: pytest.fail("Cancelled action must not execute"),
    )
    monkeypatch.setattr(
        views, "_record_copilot_action_event", lambda **kwargs: events.append(kwargs)
    )
    monkeypatch.setattr(views, "update_action_message", lambda *args: None)
    monkeypatch.setattr(views, "append_message", lambda *args: None)

    response = call_action_endpoint(
        factory,
        system_admin(),
        {
            "action_id": action["action_id"],
            "action": "cancel",
            "conversation_id": "conversation-123",
        },
    )

    assert response.status_code == 200
    assert response.data["response_type"] == "action_cancelled"
    assert response.data["query_status"] == "cancelled"
    assert response.data["intent"] == "attendance_update"
    assert events[0]["event_type"] == "COPILOT_ACTION_CANCELLED"


def test_action_approval_sanitizes_unexpected_execution_exception(
    api, monkeypatch
):
    factory, _ = api
    action = {
        "action_id": "action-error-123",
        "intent": "employee_status_update",
        "description": "Deactivate Asha Rao",
    }
    failed = []
    monkeypatch.setattr(
        views.pending_action_manager,
        "approve_action",
        lambda *args: action,
    )
    monkeypatch.setattr(
        views.write_action_executor,
        "execute_approved_action",
        lambda *_: (_ for _ in ()).throw(RuntimeError("database password")),
    )
    monkeypatch.setattr(
        views.pending_action_manager,
        "mark_failed",
        lambda *args: failed.append(args),
    )
    monkeypatch.setattr(
        views.HRCopilotActionApprovalView,
        "_record_failure",
        staticmethod(lambda *args: None),
    )

    response = call_action_endpoint(
        factory,
        system_admin(),
        {
            "action_id": action["action_id"],
            "action": "approve",
            "conversation_id": "conversation-123",
        },
    )

    assert response.status_code == 500
    assert response.data["code"] == "action_failed"
    assert "database password" not in response.data["detail"]
    assert len(failed) == 1


def test_pending_actions_view_filters_non_pending_actions(api, monkeypatch):
    factory, _ = api
    actions = {
        "pending": {
            "status": "PENDING",
            "description": "Confirm attendance change",
            "target_data": {"employee_id": 7},
            "proposed_changes": {"status": "ABSENT"},
            "current_state": {"exists": False},
            "intent": "attendance_update",
            "expires_at": "later",
            "created_at": "now",
        },
        "awaiting": {"status": "AWAITING_INFORMATION"},
    }
    captured = []
    monkeypatch.setattr(
        views.pending_action_manager,
        "get_session_actions",
        lambda *args: captured.append(args) or actions,
    )
    request = factory.get(
        "/api/hr-copilot/actions/",
        {"conversation_id": "conversation-123"},
    )
    force_authenticate(request, user=system_admin())

    response = views.HRCopilotPendingActionsView.as_view()(request)

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["pending_actions"][0]["action_id"] == "pending"
    assert captured[0] == (
        views.copilot_action_session_id(1, "conversation-123"),
        1,
    )


def test_pending_actions_without_conversation_lists_user_actions(api, monkeypatch):
    factory, _ = api
    actions = {
        "pending": {
            "status": "PENDING",
            "description": "Confirm leave request",
            "warning_message": "This cannot be undone.",
            "target_data": {"employee_id": 7},
            "proposed_changes": {"status": "PENDING"},
            "current_state": {"exists": False},
            "intent": "leave_create",
            "expires_at": "later",
            "created_at": "now",
        }
    }
    captured = []
    monkeypatch.setattr(
        views.pending_action_manager,
        "get_user_actions",
        lambda *args: captured.append(args) or actions,
    )
    request = factory.get("/api/hr-copilot/actions/")
    force_authenticate(request, user=system_admin())

    response = views.HRCopilotPendingActionsView.as_view()(request)

    assert response.status_code == 200
    assert response.data["count"] == 1
    assert response.data["pending_actions"][0]["warning_message"] == "This cannot be undone."
    assert captured == [(1,)]


def test_action_failure_persists_scoped_audit_and_event(monkeypatch):
    user = system_admin()
    pending = SimpleNamespace(
        intent="attendance_update",
        action_type="attendance_update",
        description="Update Asha Rao's attendance",
        current_state={"status": "INCOMPLETE"},
        authorization_scope={"sections": ["C"]},
        approved_at=None,
        audit_records=SimpleNamespace(
            order_by=lambda *_: SimpleNamespace(
                first=lambda: SimpleNamespace(id=733)
            )
        ),
    )
    lookup_calls = []
    audit_rows = []
    events = []
    monkeypatch.setattr(
        views,
        "CopilotPendingAction",
        SimpleNamespace(
            objects=SimpleNamespace(
                get=lambda **kwargs: lookup_calls.append(kwargs) or pending
            )
        ),
    )
    monkeypatch.setattr(
        views,
        "CopilotActionAudit",
        SimpleNamespace(
            objects=SimpleNamespace(
                create=lambda **kwargs: audit_rows.append(kwargs)
            )
        ),
    )
    monkeypatch.setattr(
        views,
        "_record_copilot_action_event",
        lambda **kwargs: events.append(kwargs),
    )
    request = SimpleNamespace(
        META={"REMOTE_ADDR": "192.0.2.10", "HTTP_USER_AGENT": "test-agent"}
    )

    views.HRCopilotActionApprovalView._record_failure(
        user, "action-733", "session-733", "x" * 2100, request
    )

    assert lookup_calls == [
        {"action_id": "action-733", "user": user, "session_id": "session-733"}
    ]
    assert len(audit_rows) == 1
    assert audit_rows[0]["error_message"] == "x" * 2000
    assert audit_rows[0]["previous_state"] == {"status": "INCOMPLETE"}
    assert audit_rows[0]["authorization_scope"] == {"sections": ["C"]}
    assert audit_rows[0]["ip_address"] == "192.0.2.10"
    assert events[0]["event_type"] == "COPILOT_ACTION_FAILED"
    assert events[0]["metadata"] == {"action_audit_id": 733}


def test_action_failure_audit_storage_error_is_best_effort(monkeypatch):
    monkeypatch.setattr(
        views,
        "CopilotPendingAction",
        SimpleNamespace(
            objects=SimpleNamespace(
                get=lambda **_: (_ for _ in ()).throw(RuntimeError("db down"))
            )
        ),
    )

    views.HRCopilotActionApprovalView._record_failure(
        system_admin(), "action-missing", "session-missing", "failure", None
    )


def test_write_planner_builds_missing_employee_follow_up_for_present_attendance():
    today = timezone.localdate()
    intent = {
        "intent": "attendance_update",
        "source": "attendance",
        "entities": {
            "date_range": {"start": today.isoformat(), "end": today.isoformat()},
            "target_status": "PRESENT",
        },
    }

    pending = write_action_planner._plan_missing_employee(
        intent,
        system_admin(),
        {"sections": ["C"], "unrestricted": False},
        "session-123",
    )

    assert pending["status"] == "AWAITING_INFORMATION"
    assert pending["action_type"] == "attendance_update"
    assert pending["validation_errors"] == [
        "employee_name",
        "check_in_time",
        "check_out_time",
    ]
    assert pending["requires_confirmation"] is True
    assert pending["target_data"]["employee_id"] is None


def test_write_planner_missing_employee_leave_follow_up_requests_reason():
    today = timezone.localdate()
    intent = {
        "intent": "leave_create",
        "source": "leave",
        "entities": {
            "date_range": {"start": today.isoformat(), "end": today.isoformat()},
        },
    }

    pending = write_action_planner._plan_missing_employee(
        intent, system_admin(), {"unrestricted": True}, "session-456"
    )

    assert pending["action_type"] == "leave_create"
    assert pending["validation_errors"] == ["employee_name", "reason"]
    assert "employee" in pending["description"].casefold()


def test_ambiguous_employee_follow_up_keeps_action_pending_and_requests_email(
    api, monkeypatch
):
    factory, _ = api
    monkeypatch.setattr(views, "record_event", lambda **kwargs: None)
    draft = {
        "action_id": "ambiguous-action",
        "action_type": "attendance_update",
        "intent": "attendance_update",
        "target_data": {"employee_id": None},
        "proposed_changes": {"status": "ABSENT"},
        "validation_errors": ["employee_name"],
        "current_state": {},
    }
    updated = {
        **draft,
        "status": "AWAITING_INFORMATION",
        "validation_errors": ["employee_email"],
        "description": "Which employee email should I use?",
    }
    monkeypatch.setattr(
        views.pending_action_manager,
        "get_awaiting_action",
        lambda *args: draft,
    )
    monkeypatch.setattr(
        views,
        "extract_pending_action_fields",
        lambda *_: {"employee_name": "Asha Rao"},
    )
    monkeypatch.setattr(
        write_action_planner,
        "_resolve_target_employee",
        lambda *args: (_ for _ in ()).throw(
            CopilotError("employee_ambiguous", "More than one employee matched")
        ),
    )
    monkeypatch.setattr(
        views.pending_action_manager,
        "update_awaiting_action",
        lambda *args: updated,
    )

    response = call_endpoint(
        factory,
        system_admin(),
        {"message": "Asha Rao", "conversation_id": "conversation-ambiguous"},
    )

    assert response.status_code == 200
    assert response.data["query_status"] == "awaiting_information"
    assert response.data["pending_action"]["validation_errors"] == ["employee_email"]


@pytest.mark.parametrize("leave_type_configured", [True, False])
def test_leave_follow_up_handles_configured_leave_type(
    api, monkeypatch, leave_type_configured
):
    factory, audit_records = api
    today = timezone.localdate().isoformat()
    draft = {
        "action_id": "leave-follow-up",
        "action_type": "leave_create",
        "intent": "leave_create",
        "target_data": {
            "employee_id": None,
            "start_date": today,
            "end_date": today,
            "reason": "Medical appointment",
        },
        "proposed_changes": {},
        "validation_errors": ["employee_name"],
        "current_state": {},
    }
    leave_type = (
        SimpleNamespace(id=17, name="Annual leave")
        if leave_type_configured
        else None
    )
    updated_actions = []
    updated = {
        **draft,
        "action_id": draft["action_id"],
        "target_data": {
            **draft["target_data"],
            "employee_id": 42,
            "employee_name": "Asha Rao",
            "leave_type_id": leave_type.id if leave_type else None,
        },
        "proposed_changes": {
            "leave_type": leave_type.name if leave_type else None
        },
        "validation_errors": [],
        "status": "PENDING",
        "description": f"Confirm Asha Rao's leave on {today}: Medical appointment",
    }
    monkeypatch.setattr(
        views.pending_action_manager,
        "get_awaiting_action",
        lambda *args: draft,
    )
    monkeypatch.setattr(
        views,
        "extract_pending_action_fields",
        lambda *_: {"employee_name": "Asha Rao"},
    )
    monkeypatch.setattr(
        write_action_planner,
        "_resolve_target_employee",
        lambda *_: {"employee_id": 42, "employee_name": "Asha Rao"},
    )
    monkeypatch.setattr(
        views,
        "LeaveType",
        SimpleNamespace(objects=SimpleNamespace(first=lambda: leave_type)),
    )

    def update_awaiting_action(*args):
        updated_actions.append(args)
        return updated

    monkeypatch.setattr(
        views.pending_action_manager,
        "update_awaiting_action",
        update_awaiting_action,
    )

    response = call_endpoint(
        factory,
        system_admin(),
        {"message": "Asha Rao", "conversation_id": "leave-follow-up-chat"},
    )

    if leave_type_configured:
        assert response.status_code == 200
        assert response.data["query_status"] == "pending_approval"
        assert response.data["pending_action"]["target_data"]["leave_type_id"] == 17
        assert response.data["pending_action"]["proposed_changes"]["leave_type"] == "Annual leave"
        assert "Confirm Asha Rao's leave" in response.data["answer"]
        assert len(updated_actions) == 1
        assert updated_actions[0][3]["validated"] is True
        assert audit_records[0].execution_result == "not_run"
    else:
        assert response.status_code == 400
        assert response.data["code"] == "no_leave_types"
        assert response.data["query_status"] == "rejected"
        assert updated_actions == []
        assert audit_records[0].execution_result == "rejected"


def test_employee_scope_denial_does_not_update_pending_action(api, monkeypatch):
    factory, _ = api
    monkeypatch.setattr(views, "record_event", lambda **kwargs: None)
    draft = {
        "action_id": "out-of-scope-action",
        "action_type": "attendance_update",
        "intent": "attendance_update",
        "target_data": {"employee_id": None},
        "proposed_changes": {"status": "ABSENT"},
        "validation_errors": ["employee_name"],
        "current_state": {},
    }
    updates = []
    monkeypatch.setattr(
        views.pending_action_manager,
        "get_awaiting_action",
        lambda *args: draft,
    )
    monkeypatch.setattr(
        views,
        "extract_pending_action_fields",
        lambda *_: {"employee_name": "Out of scope"},
    )
    monkeypatch.setattr(
        write_action_planner,
        "_resolve_target_employee",
        lambda *args: (_ for _ in ()).throw(
            CopilotError("scope_denied", "Employee is outside manager scope", 403)
        ),
    )
    monkeypatch.setattr(
        views.pending_action_manager,
        "update_awaiting_action",
        lambda *args: updates.append(args),
    )

    response = call_endpoint(
        factory,
        system_admin(),
        {"message": "Out of scope", "conversation_id": "conversation-scope"},
    )

    assert response.status_code == 403
    assert response.data["query_status"] == "rejected"
    assert updates == []


def test_ambiguous_write_intent_creates_email_clarification(api, monkeypatch):
    factory, audit_records = api
    today = timezone.localdate().isoformat()
    intent = {
        "intent": "attendance_update",
        "source": "attendance",
        "action_type": "write",
        "original_query": "Mark Asha Rao absent today",
        "entities": {
            "employee_name": "Asha Rao",
            "date_range": {"start": today, "end": today},
            "target_status": "ABSENT",
        },
    }
    stored = []
    monkeypatch.setattr(views, "record_event", lambda **kwargs: None)
    monkeypatch.setattr(views, "analyze_question", lambda *args, **kwargs: intent)
    monkeypatch.setattr(
        write_action_planner,
        "plan_write_action",
        lambda *args: (_ for _ in ()).throw(
            CopilotError("employee_ambiguous", "More than one employee matched")
        ),
    )
    monkeypatch.setattr(
        views.pending_action_manager,
        "store_pending_action",
        lambda session, action: stored.append(action) or "stored-action-id",
    )
    monkeypatch.setattr(
        views, "_record_copilot_action_event", lambda **kwargs: None
    )

    response = call_endpoint(
        factory,
        system_admin(),
        {"message": "Mark Asha Rao absent today", "conversation_id": "ambiguous-write"},
    )

    assert response.status_code == 200
    assert response.data["response_type"] == "clarification"
    assert response.data["query_status"] == "awaiting_information"
    assert response.data["pending_action"]["validation_errors"] == ["employee_email"]
    assert len(stored) == 1
    assert audit_records[0].execution_result == "awaiting_information"


@pytest.mark.parametrize(
    ("value", "checkout", "expected"),
    [
        ("09:30", False, "09:30"),
        ("9:30 p.m.", True, "21:30"),
        ("9", False, "09:00"),
        ("9", True, "21:00"),
        ("24", True, None),
        ("noon-ish", False, None),
    ],
)
def test_write_planner_normalizes_times_and_rejects_invalid_values(
    value, checkout, expected
):
    assert write_action_planner._normalize_time(value, checkout) == expected


def test_regularization_planner_creates_reviewable_request_with_normalized_times(
    monkeypatch,
):
    today = timezone.localdate()
    monkeypatch.setattr(
        write_action_planner,
        "_resolve_target_employee",
        lambda *_: {"employee_id": 42, "employee_name": "Asha Rao"},
    )
    monkeypatch.setattr(
        write_action_planner, "_resolve_target_date", lambda _: today
    )
    attendance_query = MagicMock()
    attendance_query.filter.return_value.first.return_value = None
    monkeypatch.setattr(
        write_action_module,
        "Attendance",
        SimpleNamespace(objects=attendance_query),
    )
    intent = {
        "intent": "regularization_create",
        "source": "attendance",
        "entities": {
            "request_type": "FORGOT_CHECK_IN",
            "reason": "Forgot to check in",
            "check_in_time": "9",
        },
    }

    pending = write_action_planner._plan_regularization_create(
        intent, system_admin(), {"unrestricted": True}, "session-reg"
    )

    assert pending["validated"] is True
    assert pending["target_data"]["employee_id"] == 42
    assert pending["target_data"]["requested_check_in"] == "09:00"
    assert pending["proposed_changes"] == {
        "operation": "create",
        "request_type": "FORGOT_CHECK_IN",
    }
    attendance_query.filter.assert_called_once_with(employee_id=42, date=today)


def test_regularization_planner_collects_missing_reason_before_confirmation(
    monkeypatch,
):
    today = timezone.localdate()
    monkeypatch.setattr(
        write_action_planner,
        "_resolve_target_employee",
        lambda *_: {"employee_id": 42, "employee_name": "Asha Rao"},
    )
    monkeypatch.setattr(
        write_action_planner, "_resolve_target_date", lambda _: today
    )
    attendance_query = MagicMock()
    attendance_query.filter.return_value.first.return_value = None
    monkeypatch.setattr(
        write_action_module,
        "Attendance",
        SimpleNamespace(objects=attendance_query),
    )
    intent = {
        "intent": "regularization_create",
        "source": "attendance",
        "entities": {"request_type": "FORGOT_CHECK_IN"},
    }

    pending = write_action_planner._plan_regularization_create(
        intent, system_admin(), {"unrestricted": True}, "session-reg-missing"
    )

    assert pending["validated"] is False
    assert pending["status"] == "AWAITING_INFORMATION"
    assert pending["validation_errors"] == ["reason"]


def test_leave_review_planner_requires_reason_for_denial_and_previews_approval(
    monkeypatch,
):
    today = timezone.localdate() + timedelta(days=2)
    leave = SimpleNamespace(
        id=55,
        leave_type=SimpleNamespace(name="Annual"),
        start_date=today,
        end_date=today,
        duration_days=1,
        status="PENDING",
    )
    query = MagicMock()
    query.filter.return_value = query
    query.select_related.return_value = query
    query.order_by.return_value = [leave]
    monkeypatch.setattr(
        write_action_module,
        "LeaveRequest",
        SimpleNamespace(objects=SimpleNamespace(filter=lambda **_: query)),
    )
    monkeypatch.setattr(
        write_action_planner,
        "_resolve_target_employee",
        lambda *_: {"employee_id": 42, "employee_name": "Asha Rao"},
    )
    user = system_admin()

    with pytest.raises(CopilotError) as raised:
        write_action_planner._plan_leave_review(
            {
                "intent": "leave_deny",
                "entities": {"employee_id": 42, "request_id": 55},
            },
            user,
            {"unrestricted": True},
            "session-deny",
        )
    assert raised.value.code == "review_reason_required"

    pending = write_action_planner._plan_leave_review(
        {
            "intent": "leave_approve",
            "entities": {"employee_id": 42, "request_id": 55},
        },
        user,
        {"unrestricted": True},
        "session-approve",
    )
    assert pending["proposed_changes"]["status"] == "APPROVED"
    assert "attendance records" in pending["warning_message"]


def test_regularization_review_planner_blocks_grouped_requests(monkeypatch):
    request = SimpleNamespace(
        id=21,
        employee_id=42,
        attendance_date=timezone.localdate() - timedelta(days=1),
        status="PENDING",
        days=SimpleNamespace(exists=lambda: True),
        employee=SimpleNamespace(
            user=SimpleNamespace(get_full_name=lambda: "Asha Rao", email="asha@example.test")
        ),
    )
    query = MagicMock()
    query.select_related.return_value = query
    query.filter.return_value = query
    query.order_by.return_value = [request]
    monkeypatch.setattr(
        write_action_module,
        "RegularizationRequest",
        SimpleNamespace(objects=SimpleNamespace(select_related=lambda *_: query)),
    )
    monkeypatch.setattr(
        write_action_planner,
        "_resolve_target_employee",
        lambda *_: {"employee_id": 42, "employee_name": "Asha Rao"},
    )

    with pytest.raises(CopilotError) as raised:
        write_action_planner._plan_regularization_review(
            {
                "intent": "regularization_approve",
                "entities": {"request_id": request.id},
            },
            system_admin(),
            {"unrestricted": True},
            "session-grouped",
        )

    assert raised.value.code == "unsupported_grouped_regularization"


@pytest.mark.parametrize(
    ("phrase", "offset"),
    [
        ("attendance today", 0),
        ("attendance yesterday", 1),
        ("attendance two days ago", 2),
    ],
)
def test_pipeline_applies_supported_relative_dates(phrase, offset):
    today = timezone.localdate()
    entities = {}

    pipeline._apply_explicit_date_range(phrase, entities, today)

    expected = (today - timedelta(days=offset)).isoformat()
    assert entities["date_range"] == {"start": expected, "end": expected}


@pytest.mark.parametrize("phrase", ["last week", "last 7 days"])
def test_pipeline_last_week_range_includes_today_and_previous_six_days(phrase):
    today = date(2026, 10, 13)
    entities = {}

    pipeline._apply_explicit_date_range(phrase, entities, today)

    assert entities["date_range"] == {
        "start": (today - timedelta(days=6)).isoformat(),
        "end": today.isoformat(),
    }


def test_pipeline_calendar_month_ranges_handle_year_boundary():
    today = date(2026, 1, 3)
    this_month = {}
    last_month = {}

    pipeline._apply_explicit_date_range("this month", this_month, today)
    pipeline._apply_explicit_date_range("last month", last_month, today)

    assert this_month["date_range"] == {"start": "2026-01-01", "end": "2026-01-03"}
    assert last_month["date_range"] == {"start": "2025-12-01", "end": "2025-12-31"}


def test_pipeline_this_week_starts_on_monday():
    today = date(2026, 10, 14)
    entities = {}

    pipeline._apply_explicit_date_range("this week", entities, today)

    assert entities["date_range"] == {"start": "2026-10-12", "end": "2026-10-14"}


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("attendance on 14 October 2026", {"start": "2026-10-14", "end": "2026-10-14"}),
        ("attendance from 2026-10-12 to 2026-10-14", {"start": "2026-10-12", "end": "2026-10-14"}),
    ],
)
def test_pipeline_applies_natural_and_iso_date_ranges(question, expected):
    entities = {}

    pipeline._apply_explicit_date_range(question, entities, date(2026, 10, 14))

    assert entities["date_range"] == expected


@pytest.mark.parametrize(
    ("question", "code"),
    [
        ("attendance on 2026-02-30", "invalid_date"),
        ("attendance 2026-10-12 2026-10-13 2026-10-14", "invalid_date_range"),
        ("attendance from 2026-10-14 to 2026-10-12", "invalid_date_range"),
    ],
)
def test_pipeline_rejects_malformed_iso_ranges(question, code):
    with pytest.raises(CopilotError) as error:
        pipeline._apply_explicit_date_range(question, {}, date(2026, 10, 14))

    assert error.value.code == code


@pytest.mark.parametrize(
    ("intent_name", "metric_key", "tool_name", "metric"),
    [
        (
            "leave_regularization_intelligence",
            "intelligence_metric",
            "execute_leave_regularization_intelligence",
            "leave_usage",
        ),
        (
            "workforce_intelligence",
            "workforce_metric",
            "execute_workforce_intelligence",
            "shift_assignments",
        ),
    ],
)
def test_specialized_intelligence_uses_scoped_typed_tool(
    api, monkeypatch, intent_name, metric_key, tool_name, metric
):
    factory, audit_records = api
    result = {
        "metric": metric,
        "date_range": {"start": "2026-10-01", "end": "2026-10-14"},
        "assumptions": ["Only active employees in the manager scope are included."],
        "rows": [{"employee_id": 7, "employee_name": "Asha Rao"}],
    }
    intent = {
        "intent": intent_name,
        "source": "employee",
        "action_type": "read",
        "entities": {metric_key: metric},
    }
    plan = {
        "intent": intent_name,
        "source": "employee",
        metric_key: metric,
        "filters": {},
        "employee": {"employee_id": None},
    }
    monkeypatch.setattr(views, "record_event", lambda **kwargs: None)
    monkeypatch.setattr(views, "analyze_question", lambda *args, **kwargs: intent)
    monkeypatch.setattr(views, "plan_query", lambda *args: plan)
    monkeypatch.setattr(
        views.hr_tools, tool_name, lambda **kwargs: result
    )
    monkeypatch.setattr(views, "generate_natural_answer", lambda *args, **kwargs: "Report ready.")

    response = call_endpoint(
        factory,
        system_admin(),
        {"message": f"Show {metric}", "conversation_id": f"{intent_name}-tool"},
    )

    assert response.status_code == 200
    assert response.data["data"]["rows"] == result["rows"]
    assert response.data["data"]["metadata"]["metric"] == metric
    assert response.data["data"]["metadata"]["assumptions"] == result["assumptions"]
    assert audit_records[0].execution_result == "success"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("29 September 2026", "2026-09-29"),
        ("September 29th 2026", "2026-09-29"),
        ("September 31 2026", None),
        ("some other date", None),
    ],
)
def test_pipeline_parses_natural_dates_and_rejects_impossible_dates(text, expected):
    assert pipeline._parse_natural_date_string(
        text, date(2026, 9, 1)
    ) == expected


def test_pipeline_extracts_email_scope_and_attendance_status_deterministically():
    entities = {}

    pipeline._apply_deterministic_entities(
        "Show attendance for PERSON@example.test in C2 as completed",
        "employee",
        entities,
    )

    assert entities["employee_email"] == "person@example.test"
    assert entities["section"] == "C"
    assert entities["subsection"] == "C2"
    assert entities["attendance_status"] == "PRESENT"


def test_pipeline_requires_identity_when_a_name_or_email_filter_is_requested():
    with pytest.raises(CopilotError) as raised:
        pipeline._apply_deterministic_entities(
            "Show attendance by email", "attendance", {}
        )

    assert raised.value.code == "clarification_required"


def test_pipeline_marks_live_date_scope_and_write_intent(monkeypatch):
    today = timezone.localdate().isoformat()
    monkeypatch.setattr(
        "hr_copilot.services.semantic_interpreter.semantic_interpreter.interpret_query",
        lambda *args, **kwargs: {
            "intent": "attendance_lookup",
            "source": "attendance",
            "entities": {"date_range": {"start": today, "end": today}},
        },
    )

    result = pipeline.analyze_question("Show attendance today")

    assert result["action_type"] == "read"
    assert result["entities"]["temporal_scope"]["type"] == "today"
    assert result["entities"]["temporal_scope"]["source"] == "llm_resolved"


def test_pipeline_marks_write_intents_as_approval_required(monkeypatch):
    monkeypatch.setattr(
        "hr_copilot.services.semantic_interpreter.semantic_interpreter.interpret_query",
        lambda *args, **kwargs: {
            "intent": "attendance_create",
            "source": "attendance",
            "entities": {},
        },
    )

    result = pipeline.analyze_question("Create attendance")

    assert result["action_type"] == "write"
    assert result["requires_approval"] is True


@pytest.mark.parametrize(
    ("intent_name", "expected_phrase"),
    [
        ("attendance_intelligence", "attendance metric"),
        ("leave_regularization_intelligence", "leave or regularization information"),
        ("workforce_intelligence", "workforce information"),
    ],
)
def test_pipeline_requires_a_metric_for_specialized_queries(intent_name, expected_phrase):
    with pytest.raises(CopilotError) as raised:
        pipeline.plan_query(
            {
                "intent": intent_name,
                "source": "attendance" if intent_name == "attendance_intelligence" else "employee",
                "entities": {},
            },
            {"sections": ["C"], "subsections": [], "unrestricted": False},
            system_admin(),
        )

    assert raised.value.code == "clarification_required"
    assert expected_phrase in raised.value.message.lower()


def test_pipeline_denies_an_explicit_section_outside_manager_scope():
    with pytest.raises(CopilotError) as raised:
        pipeline.plan_query(
            {
                "intent": "attendance_lookup",
                "source": "attendance",
                "entities": {"section": "D"},
            },
            {"sections": ["C"], "subsections": ["C1"], "unrestricted": False},
            system_admin(),
        )

    assert raised.value.code == "scope_denied"
    assert raised.value.status == 403


def test_pipeline_requires_identity_when_normalizer_marks_it_missing():
    with pytest.raises(CopilotError) as raised:
        pipeline.plan_query(
            {
                "intent": "employee_lookup",
                "source": "employee",
                "entities": {"employee_identity_missing": True},
            },
            {"sections": ["C"], "subsections": [], "unrestricted": False},
            system_admin(),
        )

    assert raised.value.code == "clarification_required"
    assert "name or email" in raised.value.message


@pytest.mark.parametrize(
    ("resolution", "expected_code"),
    [
        ({"status": "not_found", "employee_id": None}, "employee_not_found"),
        ({"status": "ambiguous", "employee_id": None}, "employee_ambiguous"),
    ],
)
def test_pipeline_rejects_unresolved_employee_name(
    monkeypatch, resolution, expected_code
):
    monkeypatch.setattr(
        pipeline.employee_resolver,
        "resolve_employee",
        lambda **_: SimpleNamespace(as_dict=lambda: resolution),
    )

    with pytest.raises(CopilotError) as raised:
        pipeline.plan_query(
            {
                "intent": "employee_lookup",
                "source": "employee",
                "entities": {"employee_name": "Asha Rao"},
            },
            {"sections": ["C"], "subsections": [], "unrestricted": False},
            system_admin(),
        )

    assert raised.value.code == expected_code


def test_write_planner_rejects_unsupported_regularization_type_before_lookup(monkeypatch):
    monkeypatch.setattr(
        write_action_planner,
        "_resolve_target_employee",
        lambda *_: {"employee_id": 42, "employee_name": "Asha Rao"},
    )
    monkeypatch.setattr(
        write_action_planner, "_resolve_target_date", lambda _: date(2026, 10, 12)
    )

    with pytest.raises(CopilotError) as raised:
        write_action_planner._plan_regularization_create(
            {
                "intent": "regularization_create",
                "entities": {"request_type": "UNSUPPORTED", "reason": "Fix record"},
            },
            system_admin(),
            {"unrestricted": True},
            "unsupported-type",
        )

    assert raised.value.code == "invalid_request_type"


def test_write_planner_requires_valid_shift_and_explicit_employee_status(monkeypatch):
    monkeypatch.setattr(
        write_action_planner,
        "_resolve_target_employee",
        lambda *_: {"employee_id": 42, "employee_name": "Asha Rao"},
    )
    monkeypatch.setattr(
        write_action_module,
        "Shift",
        SimpleNamespace(objects=SimpleNamespace(filter=lambda **_: SimpleNamespace(first=lambda: None))),
    )

    with pytest.raises(CopilotError) as shift_error:
        write_action_planner._plan_shift_assignment(
            {"intent": "employee_shift_assign", "entities": {"shift_name": "Night"}},
            system_admin(),
            {"unrestricted": True},
            "missing-shift",
        )
    assert shift_error.value.code == "shift_not_found"

    with pytest.raises(CopilotError) as status_error:
        write_action_planner._plan_employee_status(
            {"intent": "employee_status_update", "entities": {"employee_id": 42}},
            system_admin(),
            {"unrestricted": True},
            "missing-status",
        )
    assert status_error.value.code == "status_required"


def test_leave_planner_reports_missing_and_ambiguous_leave_types(monkeypatch):
    monkeypatch.setattr(
        write_action_planner,
        "_resolve_target_employee",
        lambda *_: {"employee_id": 42, "employee_name": "Asha Rao"},
    )
    monkeypatch.setattr(
        write_action_planner, "_resolve_target_date", lambda _: date(2026, 10, 12)
    )

    for leave_types, expected_code in (
        (FakeLeaveTypes(), "no_leave_types"),
        (
            FakeLeaveTypes(
                [SimpleNamespace(id=1, name="Annual"), SimpleNamespace(id=2, name="Medical")]
            ),
            "leave_type_ambiguous",
        ),
    ):
        monkeypatch.setattr(
            write_action_module,
            "LeaveType",
            SimpleNamespace(
                objects=SimpleNamespace(filter=lambda **_: leave_types)
            ),
        )
        with pytest.raises(CopilotError) as raised:
            write_action_planner._plan_leave_create(
                {
                    "intent": "leave_create",
                    "source": "leave",
                    "entities": {"reason": "Personal leave"},
                },
                system_admin(),
                {"unrestricted": True},
                "leave-type-validation",
            )
        assert raised.value.code == expected_code


def test_leave_planner_requests_a_reason_before_confirmation(monkeypatch):
    leave_type = SimpleNamespace(id=11, name="Annual")
    monkeypatch.setattr(
        write_action_planner,
        "_resolve_target_employee",
        lambda *_: {"employee_id": 42, "employee_name": "Asha Rao"},
    )
    monkeypatch.setattr(
        write_action_planner, "_resolve_target_date", lambda _: date(2026, 10, 12)
    )
    monkeypatch.setattr(
        write_action_module,
        "LeaveType",
        SimpleNamespace(
            objects=SimpleNamespace(filter=lambda **_: FakeLeaveTypes([leave_type]))
        ),
    )

    pending = write_action_planner._plan_leave_create(
        {"intent": "leave_create", "source": "leave", "entities": {}},
        system_admin(),
        {"unrestricted": True},
        "leave-reason-followup",
    )

    assert pending["status"] == "AWAITING_INFORMATION"
    assert pending["validated"] is False
    assert pending["validation_errors"] == ["reason"]
    assert pending["target_data"]["leave_type_id"] == leave_type.id


def test_leave_cancel_planner_requires_explicit_request_when_ambiguous(monkeypatch):
    query = MagicMock()
    query.order_by.return_value = query
    query.__getitem__.return_value = query
    query.exists.return_value = True
    query.count.return_value = 2
    monkeypatch.setattr(
        write_action_module,
        "LeaveRequest",
        SimpleNamespace(objects=SimpleNamespace(filter=lambda **_: query)),
    )
    monkeypatch.setattr(
        write_action_planner,
        "_resolve_target_employee",
        lambda *_: {"employee_id": 42, "employee_name": "Asha Rao"},
    )

    with pytest.raises(CopilotError) as raised:
        write_action_planner._plan_leave_cancel(
            {"intent": "leave_cancel", "entities": {"employee_id": 42}},
            system_admin(),
            {"unrestricted": True},
            "ambiguous-leave-cancel",
        )

    assert raised.value.code == "leave_request_ambiguous"


def test_executor_rejects_unvalidated_action_before_authorization_or_write():
    with pytest.raises(CopilotError) as raised:
        write_action_executor.execute_approved_action(
            {"validated": False}, system_admin()
        )

    assert raised.value.code == "action_not_validated"


def test_executor_revalidates_current_employee_scope(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "derive_scope",
        lambda _user: {"unrestricted": False, "sections": ["C"], "subsections": ["C1"]},
    )
    monkeypatch.setattr(
        write_executor_module.Employee,
        "objects",
        SimpleNamespace(get=lambda **_: SimpleNamespace(section="D", subsection="D1")),
    )

    with pytest.raises(CopilotError) as raised:
        write_action_executor._revalidate_authorization(
            {"target_data": {"employee_id": 42}, "authorization_scope": {"sections": ["C"]}},
            system_admin(),
        )

    assert raised.value.code == "scope_denied"
    assert raised.value.status == 403


def test_executor_rejects_action_when_target_employee_was_deleted(monkeypatch):
    monkeypatch.setattr(
        pipeline,
        "derive_scope",
        lambda _user: {"unrestricted": False, "sections": ["C"], "subsections": []},
    )

    def missing_employee(**_):
        raise write_executor_module.Employee.DoesNotExist

    monkeypatch.setattr(
        write_executor_module.Employee,
        "objects",
        SimpleNamespace(get=missing_employee),
    )

    with pytest.raises(CopilotError) as raised:
        write_action_executor._revalidate_authorization(
            {"target_data": {"employee_id": 42}}, system_admin()
        )

    assert raised.value.code == "employee_not_found"


def test_executor_rejects_unsupported_action_type_before_audit_write(monkeypatch):
    monkeypatch.setattr(
        write_executor_module.transaction, "atomic", lambda: nullcontext()
    )
    monkeypatch.setattr(write_action_executor, "_revalidate_authorization", lambda *_: None)

    with pytest.raises(CopilotError) as raised:
        write_action_executor.execute_approved_action(
            {"validated": True, "action_type": "unknown_write", "action_id": "a"},
            system_admin(),
        )

    assert raised.value.code == "unsupported_action"


@pytest.mark.parametrize(
    ("intent", "data", "expected"),
    [
        ({"intent": "absence_count"}, [], "No absent employees were found for that date and authorized scope."),
        ({"intent": "employee_lookup", "entities": {"is_active": False}}, [], "No inactive employees were found in your authorized scope."),
        ({"intent": "absence_count"}, [{"value": 1}], "1 employee was absent on that date."),
        ({"intent": "absence_count"}, [{"value": 3}], "3 employees were absent on that date."),
        ({"intent": "employee_lookup", "source": "employee"}, [{"value": 2}], "2 employees matched your question."),
        (
            {"intent": "employee_lookup", "source": "employee"},
            [{"name": "Asha Rao", "is_active": False, "employment_type": "FULL_TIME", "department": "HR", "section": "C", "subsection": "C1"}],
            "Asha Rao is an inactive full_time employee in HR, Section C, Subsection C1.",
        ),
        (
            {"intent": "attendance_lookup", "source": "attendance", "entities": {"employee_id": 7}},
            [{"first_name": "Asha", "last_name": "Rao", "date": "2026-10-12", "status": "HALF_DAY"}],
            "Asha Rao was Half day on 2026-10-12.",
        ),
        ({"intent": "employee_lookup", "source": "employee"}, [{"category": "section", "value": "C"}], "I found 1 result group(s). See the data below for details."),
    ],
)
def test_pipeline_generates_answers_for_common_result_shapes(intent, data, expected):
    assert pipeline.generate_answer(intent, data) == expected


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        ("yesterday", date(2026, 10, 13)),
        ("tomorrow", date(2026, 10, 15)),
        ("two days ago", date(2026, 10, 12)),
        ("next quarter", date(2026, 10, 14)),
    ],
)
def test_write_planner_resolves_supported_and_unknown_relative_dates(
    monkeypatch, expression, expected
):
    monkeypatch.setattr(write_action_module.timezone, "localdate", lambda: date(2026, 10, 14))
    assert write_action_planner._resolve_target_date({"temporal_expression": expression}) == expected


@pytest.mark.parametrize(
    ("status", "reason", "expected_detail"),
    [
        ("PRESENT", "", "; check-in 09:00; check-out 17:00"),
        ("LEAVE", "Family care", "; check-in cleared; check-out cleared; reason: Family care"),
        ("ABSENT", "ignored", "; check-in cleared; check-out cleared"),
        ("REMOTE", "", "Status: REMOTE"),
    ],
)
def test_attendance_description_matches_status_semantics(status, reason, expected_detail):
    result = write_action_planner._attendance_description(
        "Asha Rao", date(2026, 10, 14), status, "09:00", "17:00", reason
    )
    assert expected_detail in result


def test_pipeline_validates_departments_and_resolves_student_category(monkeypatch):
    monkeypatch.setattr(
        pipeline.Employee,
        "objects",
        SimpleNamespace(
            values_list=lambda *_args, **_kwargs: SimpleNamespace(
                distinct=lambda: ["Engineering", "Student Department"]
            )
        ),
    )

    student_plan = pipeline.plan_query(
        {
            "intent": "employee_lookup",
            "source": "employee",
            "entities": {"department": "__STUDENT_DEPARTMENT__"},
        },
        {"unrestricted": True, "sections": [], "subsections": []},
        system_admin(),
    )
    assert student_plan["filters"]["department"] == "Student Department"

    with pytest.raises(CopilotError) as raised:
        pipeline.plan_query(
            {
                "intent": "employee_lookup",
                "source": "employee",
                "entities": {"department": "Unknown"},
            },
            {"unrestricted": True, "sections": [], "subsections": []},
            system_admin(),
        )
    assert raised.value.code == "department_not_found"


def test_pipeline_requires_two_comparison_groups_before_building_a_plan():
    with pytest.raises(CopilotError) as raised:
        pipeline.plan_query(
            {
                "intent": "comparison",
                "source": "employee",
                "entities": {"comparison_subsections": ["C1"]},
            },
            {"unrestricted": True, "sections": [], "subsections": []},
            system_admin(),
        )

    assert raised.value.code == "clarification_required"
    assert "two sections" in raised.value.message


def test_attendance_update_rejects_nonexistent_status_before_reading_state(
    monkeypatch,
):
    today = timezone.localdate()
    monkeypatch.setattr(
        write_action_planner,
        "_resolve_target_employee",
        lambda *_: {"employee_id": 42, "employee_name": "Asha Rao"},
    )
    monkeypatch.setattr(
        write_action_planner, "_resolve_target_date", lambda _: today
    )
    attendance_query = MagicMock()
    monkeypatch.setattr(
        write_action_module,
        "Attendance",
        SimpleNamespace(objects=attendance_query),
    )

    with pytest.raises(CopilotError) as raised:
        write_action_planner._plan_attendance_update(
            {
                "intent": "attendance_update",
                "entities": {
                    "temporal_expression": "today",
                    "target_status": "REMOTE",
                },
            },
            system_admin(),
            {"unrestricted": True},
            "invalid-status",
        )

    assert raised.value.code == "invalid_status"
    attendance_query.filter.assert_not_called()


def test_attendance_update_rejects_checkout_before_checkin(monkeypatch):
    today = timezone.localdate()
    monkeypatch.setattr(
        write_action_planner,
        "_resolve_target_employee",
        lambda *_: {"employee_id": 42, "employee_name": "Asha Rao"},
    )
    monkeypatch.setattr(
        write_action_planner, "_resolve_target_date", lambda _: today
    )
    monkeypatch.setattr(
        write_action_module,
        "Attendance",
        SimpleNamespace(objects=MagicMock()),
    )

    with pytest.raises(CopilotError) as raised:
        write_action_planner._plan_attendance_update(
            {
                "intent": "attendance_update",
                "entities": {
                    "temporal_expression": "today",
                    "target_status": "PRESENT",
                    "check_in_time": "17:00",
                    "check_out_time": "9:00",
                },
            },
            system_admin(),
            {"unrestricted": True},
            "invalid-times",
        )

    assert raised.value.code == "invalid_attendance_time"


def test_force_checkout_requires_a_current_open_checkin(monkeypatch):
    employee = SimpleNamespace(get_effective_shift=lambda: None)
    attendance = SimpleNamespace(employee=employee)
    attendance_query = MagicMock()
    attendance_query.select_related.return_value.get.return_value = attendance
    events_query = MagicMock()
    events_query.order_by.return_value = []
    event_create = MagicMock()
    monkeypatch.setattr(
        write_executor_module,
        "Attendance",
        SimpleNamespace(objects=attendance_query),
    )
    monkeypatch.setattr(
        write_executor_module,
        "AttendanceEvent",
        SimpleNamespace(objects=SimpleNamespace(filter=lambda **_: events_query, create=event_create)),
    )

    with pytest.raises(CopilotError) as raised:
        write_action_executor._execute_force_checkout(
            {
                "target_data": {
                    "employee_id": 42,
                    "employee_name": "Asha Rao",
                    "date": "2026-10-14",
                }
            },
            system_admin(),
        )

    assert raised.value.code == "no_active_checkin"
    event_create.assert_not_called()


def test_force_checkout_appends_event_only_for_an_open_interval(monkeypatch):
    target_date = date(2026, 10, 14)
    employee = SimpleNamespace(get_effective_shift=lambda: "morning-shift")
    attendance = SimpleNamespace(
        employee=employee, recompute_from_events=MagicMock()
    )
    attendance_query = MagicMock()
    attendance_query.select_related.return_value.get.return_value = attendance
    open_event = SimpleNamespace(event_type="CHECK_IN")
    events_query = MagicMock()
    events_query.order_by.return_value = [open_event]
    created_event = SimpleNamespace(id=91)
    event_create = MagicMock(return_value=created_event)
    monkeypatch.setattr(
        write_executor_module,
        "Attendance",
        SimpleNamespace(objects=attendance_query),
    )
    monkeypatch.setattr(
        write_executor_module,
        "AttendanceEvent",
        SimpleNamespace(
            objects=SimpleNamespace(
                filter=lambda **_: events_query, create=event_create
            )
        ),
    )

    result = write_action_executor._execute_force_checkout(
        {
            "target_data": {
                "employee_id": 42,
                "employee_name": "Asha Rao",
                "date": target_date.isoformat(),
            }
        },
        system_admin(),
    )

    assert result["success"] is True
    assert result["event_id"] == 91
    event_create.assert_called_once()
    assert event_create.call_args.kwargs["event_type"] == "CHECK_OUT"
    assert event_create.call_args.kwargs["source"] == "ADMIN"
    attendance.recompute_from_events.assert_called_once_with()


@pytest.mark.parametrize("entities", [{}, {"employee_id": 42}])
def test_regularization_review_requires_an_unambiguous_target(
    monkeypatch, entities
):
    query = MagicMock()
    query.filter.return_value = query
    monkeypatch.setattr(
        write_action_module,
        "RegularizationRequest",
        SimpleNamespace(
            objects=SimpleNamespace(select_related=lambda *_: query)
        ),
    )
    query.order_by.return_value = []

    with pytest.raises(CopilotError) as raised:
        write_action_planner._plan_regularization_review(
            {
                "intent": "regularization_approve",
                "entities": entities,
            },
            system_admin(),
            {"unrestricted": True},
            "regularization-review",
        )

    assert raised.value.code == (
        "request_required" if not entities else "regularization_not_found"
    )


def test_leave_cancel_requires_a_linked_employee_profile():
    class UserWithoutEmployee:
        id = 7

        @property
        def employee(self):
            raise write_action_module.Employee.DoesNotExist

    with pytest.raises(CopilotError) as raised:
        write_action_planner._plan_leave_cancel(
            {"intent": "leave_cancel", "entities": {}},
            UserWithoutEmployee(),
            {"unrestricted": True},
            "leave-cancel-no-profile",
        )

    assert raised.value.code == "no_employee_profile"


def test_regularization_review_requires_a_request_id_when_matches_are_ambiguous(
    monkeypatch,
):
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = [object(), object()]
    monkeypatch.setattr(
        write_action_module,
        "RegularizationRequest",
        SimpleNamespace(objects=SimpleNamespace(select_related=lambda *_: query)),
    )

    with pytest.raises(CopilotError) as raised:
        write_action_planner._plan_regularization_review(
            {
                "intent": "regularization_approve",
                "entities": {"employee_id": 42},
            },
            system_admin(),
            {"unrestricted": True},
            "ambiguous-regularization",
        )

    assert raised.value.code == "regularization_ambiguous"


def test_regularization_rejection_plan_waits_for_reason_and_keeps_confirmation(
    monkeypatch,
):
    request = SimpleNamespace(
        id=81,
        employee_id=42,
        attendance_date=date(2026, 10, 13),
        status="PENDING",
        days=SimpleNamespace(exists=lambda: False),
        employee=SimpleNamespace(
            user=SimpleNamespace(
                get_full_name=lambda: "Asha Rao", email="asha@example.test"
            )
        ),
    )
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = [request]
    monkeypatch.setattr(
        write_action_module,
        "RegularizationRequest",
        SimpleNamespace(objects=SimpleNamespace(select_related=lambda *_: query)),
    )
    monkeypatch.setattr(
        write_action_planner,
        "_resolve_target_employee",
        lambda *_: {"employee_id": 42, "employee_name": "Asha Rao"},
    )

    pending = write_action_planner._plan_regularization_review(
        {
            "intent": "regularization_reject",
            "entities": {"request_id": 81},
        },
        system_admin(),
        {"unrestricted": True},
        "reject-needs-reason",
    )

    assert pending["status"] == "AWAITING_INFORMATION"
    assert pending["validation_errors"] == ["reason"]
    assert pending["requires_confirmation"] is True
    assert pending["proposed_changes"]["status"] == "REJECTED"


def test_employee_profile_query_returns_tool_data(api, monkeypatch):
    factory, _ = api
    employee_data = [{"name": "Asha Rao", "department": "Engineering"}]
    monkeypatch.setattr(views, "record_event", lambda **_: None)
    monkeypatch.setattr(
        views,
        "analyze_question",
        lambda *_args, **_kwargs: {
            "intent": "employee_lookup",
            "source": "employee",
            "action_type": "read",
            "entities": {},
        },
    )
    monkeypatch.setattr(
        views,
        "plan_query",
        lambda *_args: {
            "intent": "employee_lookup",
            "source": "employee",
            "filters": {},
            "scope": {"unrestricted": True},
            "limit": 100,
            "employee": {"status": "resolved", "employee_id": 42},
        },
    )
    monkeypatch.setattr(
        views.hr_tools,
        "get_employee_profile",
        lambda **kwargs: employee_data,
    )
    monkeypatch.setattr(views, "generate_natural_answer", lambda *_a, **_k: "Profile found.")

    response = call_endpoint(
        factory,
        system_admin(),
        {"message": "Show Asha Rao's profile", "conversation_id": "employee-profile"},
    )

    assert response.status_code == 200
    assert response.data["data"]["rows"] == employee_data
    assert response.data["data"]["columns"] == ["name", "department"]


def test_pending_actions_view_returns_safe_error_when_store_fails(api, monkeypatch):
    factory, _ = api
    monkeypatch.setattr(
        views.pending_action_manager,
        "get_user_actions",
        lambda *_: (_ for _ in ()).throw(RuntimeError("store unavailable")),
    )
    request = factory.get("/api/hr-copilot/actions/")
    force_authenticate(request, user=system_admin())

    response = views.HRCopilotPendingActionsView.as_view()(request)

    assert response.status_code == 500
    assert response.data["pending_actions"] == []
    assert response.data["count"] == 0
    assert "store unavailable" in response.data["detail"]


def test_pipeline_rejects_department_ambiguity_before_query_planning(monkeypatch):
    monkeypatch.setattr(
        "hr_copilot.services.semantic_interpreter.semantic_interpreter.interpret_query",
        lambda *_args, **_kwargs: {
            "intent": "employee_lookup",
            "source": "employee",
            "entities": {},
            "missing_information": ["department"],
        },
    )

    with pytest.raises(CopilotError) as raised:
        pipeline.analyze_question("Show department statistics")

    assert raised.value.code == "department_not_found"


def test_pipeline_fails_closed_when_an_explicit_employee_id_cannot_resolve(
    monkeypatch,
):
    monkeypatch.setattr(
        pipeline.employee_resolver,
        "resolve_employee",
        lambda **_: SimpleNamespace(
            as_dict=lambda: {"status": "not_found", "employee_id": None}
        ),
    )

    with pytest.raises(CopilotError) as raised:
        pipeline.plan_query(
            {
                "intent": "employee_lookup",
                "source": "employee",
                "entities": {"employee_id": 987654},
            },
            {"unrestricted": True, "sections": [], "subsections": []},
            system_admin(),
        )

    assert raised.value.code == "employee_not_found"


def test_pipeline_rejects_unresolved_employee_target_for_shift_intelligence(
    monkeypatch,
):
    monkeypatch.setattr(
        pipeline.employee_resolver,
        "resolve_employee",
        lambda **_: SimpleNamespace(
            as_dict=lambda: {"status": "ambiguous", "employee_id": None}
        ),
    )

    with pytest.raises(CopilotError) as raised:
        pipeline.plan_query(
            {
                "intent": "workforce_intelligence",
                "source": "employee",
                "entities": {
                    "workforce_metric": "shift_assignments",
                    "employee_name": "Asha Rao",
                },
            },
            {"unrestricted": True, "sections": [], "subsections": []},
            system_admin(),
        )

    assert raised.value.code == "employee_ambiguous"


def test_pipeline_rechecks_resolved_employee_against_current_manager_scope(
    monkeypatch,
):
    employee = SimpleNamespace(id=42)
    monkeypatch.setattr(
        pipeline.employee_resolver,
        "resolve_employee",
        lambda **_: SimpleNamespace(
            as_dict=lambda: {"status": "resolved", "employee_id": 42}
        ),
    )
    monkeypatch.setattr(
        pipeline.Employee,
        "objects",
        SimpleNamespace(filter=lambda **_: SimpleNamespace(first=lambda: employee)),
    )
    monkeypatch.setattr(
        "accounts.scope_service.employee_in_manager_scope",
        lambda *_: False,
    )

    with pytest.raises(CopilotError) as raised:
        pipeline.plan_query(
            {
                "intent": "employee_lookup",
                "source": "employee",
                "entities": {"employee_email": "asha@example.test"},
            },
            {"unrestricted": False, "sections": ["C"], "subsections": []},
            system_admin(),
        )

    assert raised.value.code == "scope_denied"
    assert raised.value.status == 403


def test_executor_rejects_cancelling_an_already_executed_action(monkeypatch):
    action = SimpleNamespace(status="EXECUTED", cancel=lambda: pytest.fail("executed action was cancelled"))
    query = SimpleNamespace(first=lambda: action)
    monkeypatch.setattr(
        write_executor_module.CopilotPendingAction,
        "objects",
        SimpleNamespace(filter=lambda **_: query),
    )

    with pytest.raises(CopilotError) as raised:
        write_executor_module.pending_action_manager.cancel_action("session", "action", 1)

    assert raised.value.code == "action_not_cancellable"


def test_executor_marks_expired_pending_action_and_records_event(monkeypatch):
    action = SimpleNamespace(
        is_expired=True,
        status="PENDING",
        action_id="expired-action-17",
        user=system_admin(),
        save=MagicMock(),
    )
    monkeypatch.setattr(
        write_executor_module.CopilotPendingAction,
        "objects",
        SimpleNamespace(get=lambda **_: action),
    )
    events = []
    monkeypatch.setattr(
        write_executor_module, "record_event", lambda **kwargs: events.append(kwargs)
    )

    with pytest.raises(CopilotError) as raised:
        write_executor_module.pending_action_manager.get_pending_action(
            "session-c", "expired-action-17", 1
        )

    assert raised.value.code == "action_expired"
    assert action.status == "EXPIRED"
    action.save.assert_called_once_with(update_fields=["status"])
    assert events[0]["event_type"] == "COPILOT_ACTION_EXPIRED"


@pytest.mark.parametrize(
    ("intent", "code"),
    [
        (
            {
                "intent": "employee_lookup",
                "source": "employee",
                "entities": {},
                "ambiguities": ["employee_identity"],
            },
            "employee_ambiguous",
        ),
        (
            {
                "intent": "employee_lookup",
                "source": "employee",
                "entities": {},
                "missing_information": ["employee_identity"],
            },
            "employee_not_found",
        ),
        (
            {
                "intent": "employee_lookup",
                "source": "employee",
                "entities": {},
                "missing_information": ["department"],
            },
            "department_not_found",
        ),
    ],
)
def test_pipeline_rejects_ambiguous_or_unresolved_required_entities(
    monkeypatch, intent, code
):
    monkeypatch.setattr(
        "hr_copilot.services.semantic_interpreter.semantic_interpreter.interpret_query",
        lambda *args, **kwargs: intent,
    )

    with pytest.raises(CopilotError) as raised:
        pipeline.analyze_question("Find the employee")

    assert raised.value.code == code


@pytest.mark.parametrize(
    ("date_range", "code"),
    [
        (None, "clarification_required"),
        (
            {"start": "2026-10-01", "end": "2026-10-02"},
            "unsupported_absence_range",
        ),
        (
            {"start": timezone.localdate().isoformat(), "end": timezone.localdate().isoformat()},
            "incomplete_absence_period",
        ),
    ],
)
def test_absence_inference_requires_one_completed_past_day(date_range, code):
    entities = {"date_range": date_range} if date_range else {}

    with pytest.raises(CopilotError) as raised:
        pipeline._validate_absence_date_range(entities)

    assert raised.value.code == code


def test_absence_inference_accepts_a_completed_past_day():
    yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()

    pipeline._validate_absence_date_range(
        {"date_range": {"start": yesterday, "end": yesterday}}
    )


@pytest.mark.parametrize("message", [None, "", "  ", 42, "x" * 2001])
def test_query_validates_message(api, message):
    factory, audit_records = api
    response = call_endpoint(factory, system_admin(), {"message": message})
    assert response.status_code == 400
    assert audit_records == []


def test_user_provided_scope_is_ignored_and_server_scope_is_returned(
    api, monkeypatch
):
    factory, audit_records = api
    monkeypatch.setattr(
        views, "execute_query", lambda sql, params: (["value"], [(3,)])
    )
    response = call_endpoint(
        factory,
        system_admin(),
        {
            "message": "How many employees are in C2?",
            "scope": {"sections": ["D"]},
        },
    )
    assert response.status_code == 200
    assert response.data["scope"] == {
        "sections": ["C"],
        "subsections": None,
    }
    assert "e.section IN" in audit_records[0].sql
    assert audit_records[0].scope_result == "passed"
    assert audit_records[0].execution_result == "success"


def test_out_of_scope_question_is_rejected_and_audited(api, monkeypatch):
    factory, audit_records = api
    monkeypatch.setattr(
        views,
        "execute_query",
        lambda *_: pytest.fail("Must not execute denied query"),
    )
    response = call_endpoint(
        factory, system_admin(), {"message": "Show attendance for Section D"}
    )
    assert response.status_code == 403
    assert response.data["query_status"] == "rejected"
    assert response.data["code"] == "scope_denied"
    assert audit_records[0].scope_result == "denied"


def test_unassigned_scope_is_rejected_and_audited(api):
    factory, audit_records = api
    unscoped = system_admin(hr_copilot_sections=[], hr_copilot_subsections=[])
    response = call_endpoint(
        factory, unscoped, {"message": "How many employees?"}
    )
    assert response.status_code == 403
    assert response.data["code"] == "scope_unassigned"
    assert audit_records[0].scope_result == "denied"


def test_success_response_obeys_structured_contract(api, monkeypatch):
    factory, audit_records = api
    monkeypatch.setattr(views, "execute_query", lambda *_: (["value"], [(2,)]))
    response = call_endpoint(
        factory, system_admin(), {"message": "How many employees are in C1?"}
    )
    assert response.status_code == 200
    assert set(response.data) == {
        "response_type",
        "answer",
        "intent",
        "scope",
        "query_status",
        "conversation_id",
        "data",
        "visualization",
    }
    assert response.data["response_type"] == "result"
    assert response.data["query_status"] == "executed"
    assert response.data["data"] == {
        "columns": ["value"],
        "rows": [{"value": 2}],
        "row_count": 1,
    }
    assert audit_records[0].sql.startswith("SELECT")
    assert "query_plan" in audit_records[0].saved_updates[0]


def test_absence_query_uses_scoped_inference_and_returns_absent_employees(
    api, monkeypatch
):
    factory, audit_records = api
    captured = {}
    monkeypatch.setattr("holidays.services.is_working_day", lambda _day: True)

    def execute(sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return ["first_name", "last_name"], [("Asha", "Rao")]

    monkeypatch.setattr(views, "execute_query", execute)
    response = call_endpoint(
        factory, system_admin(), {"message": "Who was absent yesterday?"}
    )

    assert response.status_code == 200
    assert response.data["intent"] == "absence_lookup"
    assert response.data["data"]["rows"] == [
        {"first_name": "Asha", "last_name": "Rao"}
    ]
    assert "e.section IN" in captured["sql"]
    assert "e.is_active = TRUE" in captured["sql"]
    assert "NOT EXISTS (SELECT 1 FROM attendance_attendance" in captured["sql"]
    assert (
        "NOT EXISTS (SELECT 1 FROM leave_management_leaverequest"
        in captured["sql"]
    )
    assert audit_records[0].execution_result == "success"


def test_sql_validation_rejection_is_audited(api, monkeypatch):
    factory, audit_records = api

    def reject(*_args):
        raise CopilotError("sql_rejected", "Rejected by validator")

    monkeypatch.setattr(views, "validate_sql", reject)
    response = call_endpoint(
        factory, system_admin(), {"message": "How many employees in C1?"}
    )
    assert response.status_code == 400
    assert response.data["code"] == "sql_rejected"
    assert audit_records[0].validation_result == "rejected"
    assert audit_records[0].execution_result == "rejected"


def test_database_errors_are_sanitized_and_audited(api, monkeypatch):
    factory, audit_records = api

    def fail_query(*_args):
        raise RuntimeError("password=secret database internals")

    monkeypatch.setattr(views, "execute_query", fail_query)
    response = call_endpoint(
        factory, system_admin(), {"message": "How many employees in C1?"}
    )
    assert response.status_code == 503
    assert "secret" not in response.data["detail"]
    assert response.data["code"] == "query_failed"
    assert audit_records[0].execution_result == "failed"


def test_attendance_intelligence_read_uses_typed_tool_and_metadata(
    api, monkeypatch
):
    factory, audit_records = api
    monkeypatch.setattr(
        views,
        "analyze_question",
        lambda *args, **kwargs: {
            "intent": "attendance_intelligence",
            "source": "attendance",
            "action_type": "read",
            "entities": {
                "attendance_metric": "missing_checkins",
                "date_range": {"start": "2026-09-30", "end": "2026-09-30"},
            },
        },
    )
    monkeypatch.setattr(
        views.hr_tools,
        "execute_attendance_intelligence",
        lambda **kwargs: {
            "metric": "missing_checkins",
            "date_range": {"start": "2026-09-30", "end": "2026-09-30"},
            "assumptions": ["Effective check-in events are used."],
            "rows": [{"employee_id": 7, "employee_name": "Asha Rao"}],
        },
    )
    response = call_endpoint(
        factory, system_admin(), {"message": "Who has not checked in today?"}
    )
    assert response.status_code == 200
    assert response.data["data"]["rows"] == [
        {"employee_id": 7, "employee_name": "Asha Rao"}
    ]
    assert response.data["data"]["metadata"]["metric"] == "missing_checkins"
    assert audit_records[0].sql == ""


def test_regularization_planner_rejects_invalid_times_before_creating_action(
    monkeypatch,
):
    monkeypatch.setattr(
        write_action_planner,
        "_resolve_target_employee",
        lambda *_: {"employee_id": 42, "employee_name": "Asha Rao"},
    )
    monkeypatch.setattr(
        write_action_planner, "_resolve_target_date", lambda _: date(2026, 10, 14)
    )
    attendance_query = MagicMock()
    attendance_query.filter.return_value.first.return_value = None
    monkeypatch.setattr(
        write_action_module,
        "Attendance",
        SimpleNamespace(objects=attendance_query),
    )

    with pytest.raises(CopilotError) as raised:
        write_action_planner._plan_regularization_create(
            {
                "intent": "regularization_create",
                "entities": {
                    "request_type": "FORGOT_CHECK_IN",
                    "reason": "Missed check-in",
                    "check_in_time": "not-a-time",
                },
            },
            system_admin(),
            {"unrestricted": True},
            "invalid-regularization-time",
        )

    assert raised.value.code == "invalid_regularization_time"
    attendance_query.filter.return_value.first.assert_called_once()

@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM employees_employee LIMIT 1",
        "SELECT id FROM auth_group LIMIT 1",
        "SELECT id FROM employees_employee LIMIT 1001",
        "DELETE FROM employees_employee",
    ],
)
def test_pipeline_rejects_unsafe_sql_shapes(sql):
    with pytest.raises(CopilotError) as raised:
        pipeline.validate_sql(sql)
    assert raised.value.code == "sql_rejected"


def test_pipeline_builds_comparison_and_trend_templates_with_scoped_parameters():
    comparison = {
        "source": "attendance",
        "intent": "comparison",
        "filters": {"comparison_subsections": ["C1", "C2"]},
        "scope": {"sections": ["C"], "subsections": ["C1"], "unrestricted": False},
        "limit": 100,
    }
    sql, params = pipeline.build_sql(comparison)
    assert "GROUP BY e.subsection" in sql
    assert "e.section IN" in sql
    assert params == ["C", "C1", "C1", "C2"]

    trend = {
        "source": "attendance",
        "intent": "attendance_trend",
        "filters": {},
        "scope": {"sections": ["C"], "subsections": ["C1"], "unrestricted": False},
        "limit": 50,
    }
    sql, params = pipeline.build_sql(trend)
    assert "GROUP BY a.date, a.status" in sql
    assert params == ["C", "C1", 50]


@pytest.mark.parametrize(
    ("question", "expected_message"),
    [
        ("Show attendance by name", "employee's name"),
        ("Show attendance by email", "email address"),
        ("Show attendance for employee", "name or email address"),
        ("Show employees in Section", "which section"),
        ("Show employees in subsection?", "which subsection"),
        ("Show employees in department?", "which department"),
    ],
)
def test_pipeline_requests_missing_identity_and_scope_filters(question, expected_message):
    with pytest.raises(CopilotError) as raised:
        pipeline._apply_deterministic_entities(question, "attendance", {})
    assert raised.value.code == "clarification_required"
    assert expected_message in raised.value.message.lower()


def test_regularization_planner_rejects_checkout_before_checkin(monkeypatch):
    monkeypatch.setattr(
        write_action_planner, "_resolve_target_employee",
        lambda *_: {"employee_id": 42, "employee_name": "Asha Rao"},
    )
    monkeypatch.setattr(
        write_action_planner, "_resolve_target_date", lambda _: date(2026, 10, 14)
    )
    query = MagicMock()
    query.filter.return_value.first.return_value = None
    monkeypatch.setattr(write_action_module, "Attendance", SimpleNamespace(objects=query))

    with pytest.raises(CopilotError) as raised:
        write_action_planner._plan_regularization_create(
            {
                "intent": "regularization_create",
                "entities": {
                    "request_type": "INCORRECT_ATTENDANCE",
                    "reason": "Times reversed",
                    "check_in_time": "17:00",
                    "check_out_time": "09:00",
                },
            },
            system_admin(), {"unrestricted": True}, "reversed-times",
        )
    assert raised.value.code == "invalid_regularization_time"


def test_regularization_review_filters_by_attendance_date_range(monkeypatch):
    request = SimpleNamespace(
        id=81, employee_id=42, attendance_date=date(2026, 10, 13), status="PENDING",
        days=SimpleNamespace(exists=lambda: False),
        employee=SimpleNamespace(user=SimpleNamespace(get_full_name=lambda: "Asha Rao", email="asha@example.test")),
    )
    query = MagicMock()
    query.filter.return_value = query
    query.order_by.return_value = [request]
    monkeypatch.setattr(
        write_action_module, "RegularizationRequest",
        SimpleNamespace(objects=SimpleNamespace(select_related=lambda *_: query)),
    )
    monkeypatch.setattr(
        write_action_planner, "_resolve_target_employee",
        lambda *_: {"employee_id": 42, "employee_name": "Asha Rao"},
    )
    pending = write_action_planner._plan_regularization_review(
        {
            "intent": "regularization_approve",
            "entities": {
                "employee_id": 42,
                "date_range": {"start": "2026-10-13", "end": "2026-10-13"},
            },
        }, system_admin(), {"unrestricted": True}, "review-date-range",
    )
    assert pending["target_data"]["request_id"] == 81
    query.filter.assert_any_call(attendance_date__range=("2026-10-13", "2026-10-13"))


def test_write_target_resolution_rejects_ambiguous_employee(monkeypatch):
    monkeypatch.setattr(
        write_action_module.employee_resolver, "resolve_employee",
        lambda **_: SimpleNamespace(status="ambiguous", employee_id=None),
    )
    with pytest.raises(CopilotError) as raised:
        write_action_planner._resolve_target_employee(
            {"employee_name": "Asha Rao"}, system_admin(), {"unrestricted": True}
        )
    assert raised.value.code == "employee_ambiguous"


def test_write_target_resolution_rejects_missing_self_profile(monkeypatch):
    def missing(**_):
        raise write_action_module.Employee.DoesNotExist
    manager = SimpleNamespace(
        select_related=lambda *_: SimpleNamespace(get=missing)
    )
    monkeypatch.setattr(write_action_module, "Employee", type(
        "EmployeeWithoutProfile", (), {"objects": manager, "DoesNotExist": Exception}
    ))
    with pytest.raises(CopilotError) as raised:
        write_action_planner._resolve_target_employee(
            {}, system_admin(is_system_admin=False), {"unrestricted": True}
        )
    assert raised.value.code == "employee_required"


def test_missing_employee_attendance_plan_requires_an_explicit_date():
    with pytest.raises(CopilotError) as raised:
        write_action_planner._plan_missing_employee(
            {"intent": "attendance_update", "entities": {}},
            system_admin(), {"unrestricted": True}, "missing-date",
        )
    assert raised.value.code == "attendance_date_required"


def test_pipeline_rejects_query_that_differs_from_approved_plan():
    plan = {
        "source": "employee", "intent": "employee_count", "filters": {},
        "scope": {"sections": [], "subsections": [], "unrestricted": True},
        "limit": 10,
    }
    with pytest.raises(CopilotError) as raised:
        pipeline.validate_sql("SELECT id FROM employees_employee LIMIT 10", plan)
    assert raised.value.code == "sql_rejected"


def test_conversation_context_preserves_explicit_identity_and_scoped_follow_up():
    context = {"current_employee_id": 17, "current_employee_name": "Asha Rao"}
    matched = conversation.apply_context(
        "Show Asha's attendance", {"entities": {"employee_name": "Asha"}}, context
    )
    assert matched["entities"] == {"employee_id": 17}
    explicit = conversation.apply_context(
        "Show attendance for asha@example.test",
        {"entities": {"employee_name": "Asha"}}, context,
    )
    assert explicit["entities"] == {"employee_name": "Asha"}

    follow_up = conversation.apply_context(
        "What about that request for her?", {"entities": {}},
        {"current_employee_id": 17, "current_request_id": 81,
         "current_date": "2026-10-01", "current_date_end": "2026-10-07",
         "last_intent": "leave_lookup"},
    )
    assert follow_up["entities"]["employee_id"] == 17
    assert follow_up["entities"]["request_id"] == 81
    assert follow_up["entities"]["date_range"] == {
        "start": "2026-10-01", "end": "2026-10-07"
    }

def _awaiting_write_draft(action_type, target_data, missing=None):
    return {
        "action_id": "awaiting-action",
        "action_type": action_type,
        "intent": action_type,
        "target_data": target_data,
        "proposed_changes": {"status": "PRESENT"},
        "validation_errors": list(missing or []),
        "current_state": {},
    }


def test_attendance_follow_up_waits_for_missing_employee_without_executing(api, monkeypatch):
    factory, _ = api
    draft = _awaiting_write_draft(
        "attendance_update",
        {"employee_id": None, "employee_name": None, "date": "2026-10-14", "target_status": "ABSENT"},
        ["employee_name"],
    )
    updated = {}
    monkeypatch.setattr(views.pending_action_manager, "get_awaiting_action", lambda *_: draft)
    monkeypatch.setattr(views, "extract_pending_action_fields", lambda *_: {})
    monkeypatch.setattr(views, "extract_pending_action_fields", lambda *_: {})
    monkeypatch.setattr(
        views.pending_action_manager,
        "update_awaiting_action",
        lambda _id, _user, _session, values: updated.update(values) or {**draft, **values},
    )
    response = call_endpoint(
        factory, system_admin(), {"message": "continue", "conversation_id": "missing-target"}
    )
    assert response.status_code == 200
    assert response.data["query_status"] == "awaiting_information"
    assert "employee" in response.data["answer"].lower()
    assert updated["validation_errors"] == ["employee_name"]


def test_query_cancels_session_action_without_executing_it(api, monkeypatch):
    factory, _ = api
    action = {"action_id": "session-cancel", "intent": "attendance_update", "conversation_id": "session-cancel"}
    cancelled = []
    monkeypatch.setattr(views.pending_action_manager, "get_session_actions", lambda *_: {"session-cancel": action})
    monkeypatch.setattr(views.pending_action_manager, "cancel_action", lambda *args: cancelled.append(args) or action)
    monkeypatch.setattr(views, "record_event", lambda **_: None)
    monkeypatch.setattr(views, "_record_copilot_action_event", lambda **_: None)
    monkeypatch.setattr(views, "update_action_message", lambda *args: None)
    monkeypatch.setattr(views.write_action_executor, "execute_approved_action", lambda *_: pytest.fail("cancel must not execute"))

    response = call_endpoint(
        factory, system_admin(), {"message": "cancel", "conversation_id": "session-cancel"}
    )
    assert response.status_code == 200
    assert response.data["query_status"] == "cancelled"
    assert cancelled == [(views.copilot_action_session_id(1, "session-cancel"), "session-cancel", 1)]


def test_query_marks_failed_action_when_confirmation_execution_is_denied(api, monkeypatch):
    factory, _ = api
    action = {"action_id": "session-fail", "intent": "attendance_update", "conversation_id": "session-fail"}
    failures = []
    monkeypatch.setattr(views.pending_action_manager, "get_session_actions", lambda *_: {"session-fail": action})
    monkeypatch.setattr(views.pending_action_manager, "approve_action", lambda *_: action)
    monkeypatch.setattr(
        views.write_action_executor, "execute_approved_action",
        lambda *_: (_ for _ in ()).throw(CopilotError("scope_denied", "Scope changed", 403)),
    )
    monkeypatch.setattr(views.pending_action_manager, "mark_failed", lambda *args: failures.append(args))
    monkeypatch.setattr(views, "record_event", lambda **_: None)
    monkeypatch.setattr(views.HRCopilotActionApprovalView, "_record_failure", staticmethod(lambda *args: None))
    monkeypatch.setattr(views, "_record_copilot_action_event", lambda **_: None)
    monkeypatch.setattr(views, "update_action_message", lambda *args: None)

    response = call_endpoint(
        factory, system_admin(), {"message": "confirm", "conversation_id": "session-fail"}
    )
    assert response.status_code == 403
    assert response.data["query_status"] == "rejected"
    assert response.data["code"] == "scope_denied"
    assert len(failures) == 1
