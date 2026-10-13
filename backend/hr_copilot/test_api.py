from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import ManagerScope
from hr_copilot import views
from hr_copilot.services import pipeline, write_actions as write_action_module
from hr_copilot.services.pipeline import CopilotError
from hr_copilot.services.write_actions import write_action_planner


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
