from types import SimpleNamespace

import pytest
from rest_framework.test import APIRequestFactory, force_authenticate

from hr_copilot import views
from hr_copilot.services.pipeline import CopilotError


class FakeAudit:
    def __init__(self, **values):
        self.pk = 101
        self.validation_result = "not_run"
        self.scope_result = "not_run"
        self.execution_result = "not_run"
        self.error_code = ""
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
    return factory, audit_records


def system_admin(**overrides):
    values = {
        "is_authenticated": True,
        "is_system_admin": True,
        "is_superuser": False,
        "hr_copilot_sections": ["C"],
        "hr_copilot_subsections": ["C1", "C2"],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def call_endpoint(factory, user=None, payload=None):
    request = factory.post("/api/hr-copilot/query/", payload or {}, format="json")
    if user is not None:
        force_authenticate(request, user=user)
    return views.HRCopilotQueryView.as_view()(request)


def test_query_requires_authentication(api):
    factory, audit_records = api
    response = call_endpoint(factory)
    assert response.status_code == 401
    assert audit_records == []


def test_query_requires_system_admin(api):
    factory, audit_records = api
    employee = system_admin(is_system_admin=False)
    response = call_endpoint(factory, employee, {"message": "How many employees?"})
    assert response.status_code == 403
    assert response.data["detail"] == "System Admin access is required."
    assert audit_records == []


@pytest.mark.parametrize("message", [None, "", "  ", 42, "x" * 2001])
def test_query_validates_message(api, message):
    factory, audit_records = api
    response = call_endpoint(factory, system_admin(), {"message": message})
    assert response.status_code == 400
    assert audit_records == []


def test_user_provided_scope_is_ignored_and_server_scope_is_returned(api, monkeypatch):
    factory, audit_records = api
    monkeypatch.setattr(views, "execute_query", lambda sql, params: (["value"], [(3,)]))
    response = call_endpoint(
        factory,
        system_admin(),
        {"message": "How many employees are in C2?", "scope": {"sections": ["D"]}},
    )
    assert response.status_code == 200
    assert response.data["scope"] == {"sections": ["C"], "subsections": ["C1", "C2"]}
    assert "e.section IN" in audit_records[0].sql
    assert audit_records[0].scope_result == "passed"
    assert audit_records[0].execution_result == "success"


def test_out_of_scope_question_is_rejected_and_audited(api, monkeypatch):
    factory, audit_records = api
    monkeypatch.setattr(views, "execute_query", lambda *_: pytest.fail("Must not execute denied query"))
    response = call_endpoint(factory, system_admin(), {"message": "Show attendance for Section D"})
    assert response.status_code == 403
    assert response.data["query_status"] == "rejected"
    assert response.data["code"] == "scope_denied"
    assert audit_records[0].scope_result == "denied"


def test_unassigned_scope_is_rejected_and_audited(api):
    factory, audit_records = api
    unscoped = system_admin(hr_copilot_sections=[], hr_copilot_subsections=[])
    response = call_endpoint(factory, unscoped, {"message": "How many employees?"})
    assert response.status_code == 403
    assert response.data["code"] == "scope_unassigned"
    assert audit_records[0].scope_result == "denied"


def test_success_response_obeys_structured_contract(api, monkeypatch):
    factory, audit_records = api
    monkeypatch.setattr(views, "execute_query", lambda *_: (["value"], [(2,)]))
    response = call_endpoint(factory, system_admin(), {"message": "How many employees are in C1?"})
    assert response.status_code == 200
    assert set(response.data) == {"answer", "intent", "scope", "query_status", "data", "visualization"}
    assert response.data["query_status"] == "executed"
    assert response.data["data"] == {"columns": ["value"], "rows": [{"value": 2}], "row_count": 1}
    assert audit_records[0].sql.startswith("SELECT")
    assert "query_plan" in audit_records[0].saved_updates[0]


def test_absence_query_uses_scoped_inference_and_returns_absent_employees(api, monkeypatch):
    factory, audit_records = api
    captured = {}

    def execute(sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return ["first_name", "last_name"], [("Asha", "Rao")]

    monkeypatch.setattr(views, "execute_query", execute)
    response = call_endpoint(factory, system_admin(), {"message": "Who was absent yesterday?"})

    assert response.status_code == 200
    assert response.data["intent"] == "absence_lookup"
    assert response.data["data"]["rows"] == [{"first_name": "Asha", "last_name": "Rao"}]
    assert "e.section IN" in captured["sql"]
    assert "e.is_active = TRUE" in captured["sql"]
    assert "NOT EXISTS (SELECT 1 FROM attendance_attendance" in captured["sql"]
    assert "NOT EXISTS (SELECT 1 FROM leave_management_leaverequest" in captured["sql"]
    assert audit_records[0].execution_result == "success"


def test_sql_validation_rejection_is_audited(api, monkeypatch):
    factory, audit_records = api

    def reject(*_args):
        raise CopilotError("sql_rejected", "Rejected by validator")

    monkeypatch.setattr(views, "validate_sql", reject)
    response = call_endpoint(factory, system_admin(), {"message": "How many employees in C1?"})
    assert response.status_code == 400
    assert response.data["code"] == "sql_rejected"
    assert audit_records[0].validation_result == "rejected"
    assert audit_records[0].execution_result == "rejected"


def test_database_errors_are_sanitized_and_audited(api, monkeypatch):
    factory, audit_records = api

    def fail_query(*_args):
        raise RuntimeError("password=secret database internals")

    monkeypatch.setattr(views, "execute_query", fail_query)
    response = call_endpoint(factory, system_admin(), {"message": "How many employees in C1?"})
    assert response.status_code == 503
    assert "secret" not in response.data["detail"]
    assert response.data["code"] == "query_failed"
    assert audit_records[0].execution_result == "failed"
