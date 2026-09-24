from contextlib import nullcontext
from datetime import date, datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from django.utils import timezone

from .services.pipeline import (
    CopilotError,
    analyze_question,
    build_sql,
    derive_scope,
    execute_query,
    generate_answer,
    plan_query,
    serialize_result,
    validate_sql,
)


@pytest.mark.parametrize(
    ("question", "expected_intent", "expected_source"),
    [
        ("How many employees are in C1?", "employee_count", "employee"),
        ("Who was absent yesterday?", "absence_lookup", "employee"),
        ("How many employees were absent yesterday?", "absence_count", "employee"),
        ("Show pending leaves in C2.", "leave_lookup", "leave"),
        ("How many interns are in Section C?", "employee_count", "employee"),
        ("Compare attendance between C1 and C2", "comparison", "attendance"),
        ("Show attendance for last month", "attendance_lookup", "attendance"),
        ("Show approved leave requests from 2026-01-01", "leave_lookup", "leave"),
        ("Show attendance from 2026-02-01 to 2026-02-03", "attendance_lookup", "attendance"),
        ("List inactive employees in Section B", "employee_lookup", "employee"),
    ],
)
def test_intent_examples(question, expected_intent, expected_source):
    intent = analyze_question(question)
    assert intent["intent"] == expected_intent
    assert intent["source"] == expected_source


def test_employee_count_extracts_type_and_subsection():
    intent = analyze_question("How many interns are in Section C2?")
    assert intent["entities"] == {
        "section": "C",
        "subsection": "C2",
        "employee_type": "INTERN",
    }


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Show attendance for Section C", "today"),
        ("Show attendance for Subsection C1", "today"),
        ("Show attendance for Section C today", "today"),
        ("Show attendance for Section C yesterday", "yesterday"),
        ("Show attendance for Section C for the last 7 days", "range"),
        ("Show attendance for 2026-09-01", "date"),
    ],
)
def test_attendance_temporal_scope_is_deterministic(question, expected):
    intent = analyze_question(question)
    assert intent["entities"]["temporal_scope"]["type"] == expected
    assert intent["entities"]["date_range"]
    if expected == "today" and "today" not in question.casefold():
        assert intent["entities"]["temporal_scope"]["source"] == "default"


def test_llm_cannot_override_default_attendance_date(monkeypatch):
    today = timezone.localdate().isoformat()
    monkeypatch.setattr(
        "hr_copilot.services.llm.get_structured_intent",
        lambda *_: {"intent": "attendance_lookup", "source": "attendance", "entities": {"section": "C"}},
    )
    entities = analyze_question("Show attendance for Section C")["entities"]
    assert entities["date_range"] == {"start": today, "end": today}
    assert entities["temporal_scope"]["source"] == "default"


@pytest.mark.parametrize(
    ("question", "message"),
    [
        ("Show attendance for name or email", "name or email"),
        ("Show attendance for employee", "name or email"),
        ("Show attendance by name", "employee's name"),
        ("Show attendance by email", "email address"),
        ("Show attendance for Section", "section"),
        ("Show attendance for subsection", "subsection"),
        ("How many are in department", "department"),
    ],
)
def test_missing_required_entity_asks_for_clarification(question, message):
    with pytest.raises(CopilotError, match=message):
        analyze_question(question)


def test_employee_resolution_requires_unique_database_match(monkeypatch):
    intent = {"intent": "attendance_lookup", "source": "attendance", "entities": {"employee_email": "person@example.com"}}
    match = MagicMock()
    match.values_list.return_value = [12]
    manager = MagicMock()
    manager.filter.return_value = match
    monkeypatch.setattr("hr_copilot.services.pipeline.Employee.objects", manager)
    plan = plan_query(intent, {"sections": None, "subsections": None, "unrestricted": True})
    assert plan["employee"] == {"status": "resolved", "employee_id": 12}
    sql, params = build_sql(plan)
    assert "e.id = %s" in sql
    assert 12 in params


@pytest.mark.parametrize("ids,code", [([], "employee_not_found"), ([1, 2], "employee_ambiguous")])
def test_employee_resolution_rejects_unknown_or_ambiguous(monkeypatch, ids, code):
    intent = {"intent": "attendance_lookup", "source": "attendance", "entities": {"employee_email": "person@example.com"}}
    match = MagicMock()
    match.values_list.return_value = ids
    manager = MagicMock()
    manager.filter.return_value = match
    monkeypatch.setattr("hr_copilot.services.pipeline.Employee.objects", manager)
    with pytest.raises(CopilotError) as raised:
        plan_query(intent, {"sections": None, "subsections": None, "unrestricted": True})
    assert raised.value.code == code


def test_active_inactive_filters_use_employee_is_active_column():
    for question, value in (("Show active employees", True), ("Show inactive employees", False)):
        intent = analyze_question(question)
        sql, params = build_sql(plan_query(
            intent,
            {"sections": ["C"], "subsections": ["C1"], "unrestricted": False},
        ))
        assert "e.is_active = %s" in sql
        assert value in params


def test_department_is_validated_against_existing_employee_values(monkeypatch):
    intent = {"intent": "employee_count", "source": "employee", "entities": {"department": "Student Department"}}
    manager = MagicMock()
    manager.values_list.return_value.distinct.return_value = ["Student Department", "Engineering"]
    monkeypatch.setattr("hr_copilot.services.pipeline.Employee.objects", manager)
    sql, params = build_sql(plan_query(
        intent,
        {"sections": ["C"], "subsections": None, "unrestricted": False},
    ))
    assert "e.department = %s" in sql
    assert "Student Department" in params


def test_invalid_department_is_not_treated_as_empty_results(monkeypatch):
    intent = {"intent": "employee_count", "source": "employee", "entities": {"department": "Nonexistent"}}
    manager = MagicMock()
    manager.values_list.return_value.distinct.return_value = ["Engineering"]
    monkeypatch.setattr("hr_copilot.services.pipeline.Employee.objects", manager)
    with pytest.raises(CopilotError) as raised:
        plan_query(intent, {"sections": None, "subsections": None, "unrestricted": True})
    assert raised.value.code == "department_not_found"


def test_today_and_yesterday_are_local_dates():
    today = timezone.localdate()
    assert analyze_question("Show attendance today")["entities"]["date_range"] == {
        "start": today.isoformat(), "end": today.isoformat()
    }
    assert analyze_question("Show attendance yesterday")["entities"]["date_range"] == {
        "start": date.fromordinal(today.toordinal() - 1).isoformat(),
        "end": date.fromordinal(today.toordinal() - 1).isoformat(),
    }


def test_absence_intent_uses_yesterday_and_deterministic_rule(monkeypatch):
    monkeypatch.setattr(
        "hr_copilot.services.llm.get_structured_intent",
        lambda *_: pytest.fail("Absence intent must use its deterministic business rule"),
    )
    yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()

    intent = analyze_question("Who was absent yesterday?")

    assert intent == {
        "intent": "absence_lookup",
        "source": "employee",
        "entities": {"date_range": {"start": yesterday, "end": yesterday}},
    }


@pytest.mark.parametrize(
    ("question", "code"),
    [
        ("Who was absent?", "clarification_required"),
        ("Who was absent today?", "incomplete_absence_period"),
        ("Who was absent from 2026-01-01 to 2026-01-03?", "unsupported_absence_range"),
    ],
)
def test_absence_requires_a_single_completed_past_day(question, code):
    with pytest.raises(CopilotError) as raised:
        analyze_question(question)
    assert raised.value.code == code


def test_last_month_uses_calendar_month_boundaries():
    today = timezone.localdate()
    end = date.fromordinal(today.replace(day=1).toordinal() - 1)
    start = end.replace(day=1)
    assert analyze_question("Show attendance for last month")["entities"]["date_range"] == {
        "start": start.isoformat(), "end": end.isoformat()
    }


@pytest.mark.parametrize(
    ("question", "code"),
    [
        ("Show attendance on 2026-02-30", "invalid_date"),
        ("Show attendance from 2026-02-10 to 2026-02-01", "invalid_date_range"),
        ("Show attendance over last year", "unsupported_date_range"),
        ("Show attendance with dates 2026-01-01, 2026-02-01, 2026-03-01", "invalid_date_range"),
        ("Show leave balance for C1", "unsupported_metric"),
    ],
)
def test_unsupported_or_invalid_date_and_balance_questions_fail_closed(question, code):
    with pytest.raises(CopilotError) as raised:
        analyze_question(question)
    assert raised.value.code == code


@pytest.mark.parametrize("question", ["Show data for BR-1", "Business region BR-2 attendance"])
def test_br_questions_are_rejected_when_schema_has_no_br(question):
    with pytest.raises(CopilotError, match="BR is not represented"):
        analyze_question(question)


def test_unknown_question_has_unknown_intent():
    assert analyze_question("Tell me a joke") == {
        "intent": "unknown", "source": None, "entities": {}
    }


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("Show attendance for Section D", "section"),
        ("How many employees are in D2?", "subsection"),
    ],
)
def test_out_of_scope_request_is_denied(question, expected):
    intent = analyze_question(question)
    scope = {"sections": ["C"], "subsections": ["C1", "C2"], "unrestricted": False}
    with pytest.raises(CopilotError) as raised:
        plan_query(intent, scope)
    assert raised.value.code == "scope_denied"
    assert raised.value.message.startswith("You don’t have access")


def test_comparison_denied_if_any_requested_subsection_is_out_of_scope():
    intent = analyze_question("Compare attendance between C1 and D2")
    scope = {"sections": ["C"], "subsections": ["C1"], "unrestricted": False}
    with pytest.raises(CopilotError, match="one or more"):
        plan_query(intent, scope)


def test_comparison_query_groups_both_authorized_subsections():
    intent = analyze_question("Compare attendance between C1 and C2")
    scope = {"sections": ["C"], "subsections": ["C1", "C2"], "unrestricted": False}
    plan = plan_query(intent, scope)
    sql, params = build_sql(plan)
    assert "e.subsection AS scope" in sql
    assert params.count("C1") == 2
    assert params.count("C2") == 2


def test_absence_lookup_excludes_attendance_and_approved_leave_and_honors_scope():
    intent = analyze_question("Who was absent yesterday in C1?")
    scope = {"sections": ["C"], "subsections": ["C1", "C2"], "unrestricted": False}
    plan = plan_query(intent, scope)
    sql, params = build_sql(plan)

    assert "e.is_active = TRUE" in sql
    assert "e.date_joined <= %s" in sql
    assert "NOT EXISTS (SELECT 1 FROM attendance_attendance" in sql
    assert "NOT EXISTS (SELECT 1 FROM leave_management_leaverequest" in sql
    assert "approved_leave.status = 'APPROVED'" in sql
    assert "e.subsection IN" in sql
    assert params[:5] == ["C", "C1", "C2", "C", "C1"]
    assert params[-5:-1] == [intent["entities"]["date_range"]["start"]] * 4
    assert params[-1] == 100
    assert validate_sql(sql, plan)


def test_absence_count_uses_distinct_active_employee_count():
    intent = analyze_question("How many employees were absent yesterday?")
    sql, params = build_sql(plan_query(
        intent,
        {"sections": None, "subsections": None, "unrestricted": True},
    ))

    assert sql.startswith("SELECT COUNT(DISTINCT e.id) AS value")
    assert "e.is_active = TRUE" in sql
    assert "e.date_joined <= %s" in sql
    assert params == [intent["entities"]["date_range"]["start"]] * 4


def test_absence_question_requires_completed_past_date_when_planned():
    intent = {"intent": "absence_lookup", "source": "employee", "entities": {}}
    with pytest.raises(CopilotError) as raised:
        plan_query(intent, {"sections": None, "subsections": None, "unrestricted": True})
    assert raised.value.code == "clarification_required"


def test_ambiguous_comparison_requests_clarification():
    with pytest.raises(CopilotError, match="Which two"):
        analyze_question("Compare attendance by section")


def test_empty_system_admin_scope_is_denied():
    user = SimpleNamespace(is_superuser=False, hr_copilot_sections=[], hr_copilot_subsections=[])
    with pytest.raises(CopilotError) as raised:
        derive_scope(user)
    assert raised.value.code == "scope_unassigned"


def test_subsection_scope_derives_its_section():
    user = SimpleNamespace(is_superuser=False, hr_copilot_sections=[], hr_copilot_subsections=["c2"])
    assert derive_scope(user) == {
        "sections": ["C"], "subsections": ["C2"], "unrestricted": False
    }


def test_superuser_gets_unrestricted_scope():
    user = SimpleNamespace(is_superuser=True, hr_copilot_sections=[], hr_copilot_subsections=[])
    assert derive_scope(user)["unrestricted"] is True


def test_bound_params_and_authenticated_scope_are_in_query():
    intent = analyze_question("How many employees are in C2?")
    scope = {"sections": ["C"], "subsections": ["C1", "C2"], "unrestricted": False}
    sql, params = build_sql(plan_query(intent, scope))
    assert "e.section IN" in sql
    assert "e.subsection IN" in sql
    assert params == ["C", "C1", "C2", "C", "C2"]
    assert "C2" not in sql


def test_employee_name_resolves_to_exact_id():
    intent = analyze_question("Find employee named Tanvi Kad in C1")
    scope = {"sections": ["C"], "subsections": ["C1"], "unrestricted": False}
    match = MagicMock()
    match.values_list.return_value = [9]
    manager = MagicMock()
    manager.filter.return_value = match
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("hr_copilot.services.pipeline.Employee.objects", manager)
    employee = MagicMock(section="C", subsection="C1")
    manager.filter.return_value.only.return_value.first.return_value = employee
    try:
        sql, params = build_sql(plan_query(intent, scope))
        assert "e.id = %s" in sql
        assert 9 in params
    finally:
        monkeypatch.undo()


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM employees_employee",
        "SELECT * FROM auth_group",
        "SELECT 1; DROP TABLE accounts_user",
        "UPDATE employees_employee SET is_active = false",
        "SELECT * FROM employees_employee JOIN auth_group ON true",
    ],
)
def test_unsafe_sql_is_rejected(sql):
    with pytest.raises(CopilotError):
        validate_sql(sql)


def test_query_must_match_the_approved_template():
    plan = {
        "source": "employee", "intent": "employee_count", "filters": {},
        "scope": {"sections": ["C"], "subsections": None, "unrestricted": False},
        "limit": 100,
    }
    sql, _ = build_sql(plan)
    assert validate_sql(sql, plan)
    with pytest.raises(CopilotError, match="approved query template"):
        validate_sql(sql.replace("COUNT(DISTINCT e.id)", "COUNT(*)"), plan)


def test_generated_queries_keep_injection_text_out_of_sql_and_params():
    question = "How many employees are in C1? DROP TABLE accounts_user"
    intent = analyze_question(question)
    scope = {"sections": ["C"], "subsections": ["C1"], "unrestricted": False}
    sql, params = build_sql(plan_query(intent, scope))
    assert validate_sql(sql)
    assert "DROP" not in sql.upper()
    assert "DROP" not in " ".join(map(str, params)).upper()


@pytest.mark.parametrize(
    ("intent", "source", "from_table"),
    [
        ("employee_lookup", "employee", "employees_employee"),
        ("attendance_lookup", "attendance", "attendance_attendance"),
        ("leave_lookup", "leave", "leave_management_leaverequest"),
        ("attendance_trend", "attendance", "attendance_attendance"),
        ("leave_trend", "leave", "leave_management_leaverequest"),
        ("employee_summary", "employee", "employees_employee"),
    ],
)
def test_supported_query_templates_use_only_expected_source(intent, source, from_table):
    plan = {
        "source": source, "intent": intent, "filters": {},
        "scope": {"sections": ["C"], "subsections": ["C1"], "unrestricted": False},
        "limit": 100,
    }
    sql, params = build_sql(plan)
    assert from_table in sql
    assert validate_sql(sql, plan)
    bounded_list = intent.endswith(("lookup", "trend"))
    assert params == ["C", "C1"] + ([100] if bounded_list else [])


def test_read_query_runs_in_read_only_transaction_with_timeout(monkeypatch):
    cursor = MagicMock()
    cursor.description = [("value", int)]
    cursor.fetchall.return_value = [(4,)]
    cursor_context = MagicMock()
    cursor_context.__enter__.return_value = cursor
    monkeypatch.setattr("django.db.transaction.atomic", nullcontext)
    monkeypatch.setattr("hr_copilot.services.pipeline.connection.cursor", lambda: cursor_context)

    columns, rows = execute_query("SELECT 4 AS value", [])

    assert columns == ["value"]
    assert rows == [(4,)]
    assert cursor.execute.call_args_list[0].args[0] == "SET TRANSACTION READ ONLY"
    assert cursor.execute.call_args_list[1].args[0] == "SET LOCAL statement_timeout = '5000ms'"
    assert cursor.execute.call_args_list[2].args == ("SELECT 4 AS value", [])


def test_result_values_are_json_safe_and_answers_use_returned_counts():
    moment = datetime(2026, 9, 24, tzinfo=datetime_timezone.utc)
    data = serialize_result(
        ["date", "duration", "decimal", "nothing"],
        [(moment, timedelta(hours=2), Decimal("2.5"), None)],
    )
    assert data == [{
        "date": moment.isoformat(), "duration": "2:00:00", "decimal": "2.5", "nothing": None
    }]
    assert generate_answer({"source": "employee"}, [{"value": 3}]) == "3 employees matched your question."
    assert generate_answer({"source": "leave"}, []) == "No matching HR records were found for your authorized scope and filters."
