import re
from datetime import date, timedelta

import sqlparse
from django.db import connection
from django.utils import timezone
from employees.models import Employee

MAX_ROWS = 100
ALLOWED_TABLES = {
    "employees_employee", "accounts_user", "attendance_attendance",
    "leave_management_leaverequest", "leave_management_leavetype",
}
FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|call|do|execute|"
    r"comment|vacuum|attach|detach|pragma|set|reset|union|with)\b", re.IGNORECASE
)


class CopilotError(Exception):
    def __init__(self, code, message, status=400):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


def analyze_question(question):
    """Extract only supported entities from natural language; never accept SQL."""
    lower = question.strip().casefold()
    is_absence_question = bool(re.search(r"\b(absent|absence)\b", lower))
    if re.search(r"\b(br|business region)\b", lower):
        raise CopilotError("unsupported_entity", "BR is not represented in the current HR data model.")
    if re.search(r"\bleave\s+balances?\b", lower):
        raise CopilotError("unsupported_metric", "Leave balances use policy calculations and are not supported by this Copilot query version.")

    from .llm import get_structured_intent

    # Absence has a precise, schema-based definition below. Keep its intent
    # deterministic so an LLM cannot reinterpret the business rule.
    structured = None if is_absence_question else get_structured_intent(question)
    if structured is not None:
        intent = structured
        entities = intent["entities"]
        _apply_deterministic_entities(question, intent["source"], entities)
        today = timezone.localdate()
        if intent["source"] != "employee" or not intent["intent"].startswith("absence_"):
            _apply_explicit_date_range(question, entities, today)
            _apply_temporal_scope(question, intent["source"], intent["intent"], entities, today)
        return intent
    entities = {}

    sub = re.search(r"\bsection\s+([a-z])\s*[- ]?([0-9]+)\b|\b([a-z])([0-9]+)\b", lower)
    if sub:
        letter = sub.group(1) or sub.group(3)
        number = sub.group(2) or sub.group(4)
        entities["section"] = letter.upper()
        entities["subsection"] = letter.upper() + number
    else:
        section = re.search(r"\bsection\s+([a-z])\b", lower)
        if section:
            entities["section"] = section.group(1).upper()
    if "compare" in lower or "comparison" in lower:
        compared = sorted({value.upper() for value in re.findall(r"\b([a-z][0-9]+)\b", lower)})
        if len(compared) >= 2:
            entities["comparison_subsections"] = compared
            entities.pop("subsection", None)
        else:
            raise CopilotError("clarification_required", "Which two sections or sub-sections should I compare?")

    employee_type = re.search(r"\b(interns?|contract(?:ors)?|permanent)\b", lower)
    if employee_type:
        word = employee_type.group(1)
        entities["employee_type"] = "INTERN" if word.startswith("intern") else "CONTRACT" if word.startswith("contract") else "PERMANENT"
    if re.search(r"\binactive\b", lower):
        entities["is_active"] = False
    elif re.search(r"\bactive\b", lower):
        entities["is_active"] = True
    _apply_deterministic_entities(question, None, entities)
    leave_status = re.search(r"\b(pending|approved|denied|cancelled)\b", lower)
    attendance_status = re.search(r"\b(present|incomplete|on leave|leave)\b", lower)
    if leave_status:
        entities["leave_status"] = leave_status.group(1).upper()
    elif attendance_status:
        word = attendance_status.group(1)
        entities["attendance_status"] = "LEAVE" if word in ("leave", "on leave") else word.upper()

    today = timezone.localdate()
    if "yesterday" in lower:
        yesterday = (today - timedelta(days=1)).isoformat()
        entities["date_range"] = {"start": yesterday, "end": yesterday}
    elif "today" in lower:
        today_iso = today.isoformat()
        entities["date_range"] = {"start": today_iso, "end": today_iso}
    elif "last week" in lower or "last 7 days" in lower:
        entities["date_range"] = {"start": (today - timedelta(days=6)).isoformat(), "end": today.isoformat()}
    elif "last month" in lower:
        last_month_end = today.replace(day=1) - timedelta(days=1)
        entities["date_range"] = {"start": date(last_month_end.year, last_month_end.month, 1).isoformat(), "end": last_month_end.isoformat()}
    else:
        exact_dates = re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", lower)
        if exact_dates:
            if len(exact_dates) > 2:
                raise CopilotError("invalid_date_range", "Use one date or a date range with two ISO dates.")
            try:
                start = date.fromisoformat(exact_dates[0])
                end = date.fromisoformat(exact_dates[-1])
            except ValueError as error:
                raise CopilotError("invalid_date", "Use a valid date in YYYY-MM-DD format.") from error
            if start > end:
                raise CopilotError("invalid_date_range", "The start date must be on or before the end date.")
            entities["date_range"] = {"start": start.isoformat(), "end": end.isoformat()}
        elif re.search(r"\b(last year|this week|this month|last quarter|last 30 days)\b", lower):
            raise CopilotError("unsupported_date_range", "That date range is not supported yet. Try today, yesterday, last week, last month, or an ISO date.")

    if is_absence_question:
        source = "employee"
    elif re.search(r"\b(attendance|present|incomplete|absent|check.?in|check.?out)\b", lower):
        source = "attendance"
    elif re.search(r"\b(leave|leaves|vacation|time off)\b", lower):
        source = "leave"
    elif re.search(r"\b(employees?|staff|interns?|contractors?|permanent)\b", lower):
        source = "employee"
    else:
        source = None

    count = bool(re.search(r"\b(how many|count|number of|total)\b", lower))
    summary = bool(re.search(r"\b(summary|overview|breakdown)\b", lower))
    trend = bool(re.search(r"\b(trend|over time|by day|daily|weekly|monthly|compare|comparison)\b", lower))
    if source is None:
        name = "unknown"
    elif "compare" in lower:
        name = "comparison"
    elif is_absence_question:
        name = "absence_count" if count else "absence_lookup"
    elif source == "employee":
        name = "employee_count" if count else "employee_summary" if summary or trend else "employee_lookup"
    elif source == "attendance":
        name = "attendance_trend" if trend else "attendance_summary" if count or summary else "attendance_lookup"
    else:
        name = "leave_trend" if trend else "leave_summary" if count or summary else "leave_lookup"
    intent = {"intent": name, "source": source, "entities": entities}
    if not is_absence_question:
        _apply_temporal_scope(question, source, name, entities, today)
    if is_absence_question:
        _validate_absence_date_range(entities)
    return intent


def _apply_temporal_scope(question, source, intent_name, entities, today):
    lower = question.casefold()
    if source == "attendance" and not entities.get("date_range") and intent_name in ("attendance_lookup", "attendance_summary", "attendance_count"):
        today_iso = today.isoformat()
        entities["date_range"] = {"start": today_iso, "end": today_iso}
        entities["temporal_scope"] = {"type": "today", "start_date": today_iso, "end_date": today_iso, "source": "default"}
    elif entities.get("date_range"):
        start, end = entities["date_range"]["start"], entities["date_range"]["end"]
        scope_type = "date" if start == end else "range"
        if start == today.isoformat():
            scope_type = "today"
        elif start == (today - timedelta(days=1)).isoformat() and end == start:
            scope_type = "yesterday"
        entities["temporal_scope"] = {"type": scope_type, "start_date": start, "end_date": end, "source": "explicit"}


def _apply_explicit_date_range(question, entities, today):
    lower = question.casefold()
    if "yesterday" in lower:
        value = (today - timedelta(days=1)).isoformat()
        entities["date_range"] = {"start": value, "end": value}
    elif re.search(r"\btoday\b", lower):
        value = today.isoformat()
        entities["date_range"] = {"start": value, "end": value}
    elif "last week" in lower or "last 7 days" in lower:
        entities["date_range"] = {"start": (today - timedelta(days=6)).isoformat(), "end": today.isoformat()}
    elif "last month" in lower:
        end = today.replace(day=1) - timedelta(days=1)
        entities["date_range"] = {"start": date(end.year, end.month, 1).isoformat(), "end": end.isoformat()}
    else:
        dates = re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", lower)
        if dates:
            if len(dates) > 2:
                raise CopilotError("invalid_date_range", "Use one date or a date range with two ISO dates.")
            try:
                start, end = date.fromisoformat(dates[0]), date.fromisoformat(dates[-1])
            except ValueError as error:
                raise CopilotError("invalid_date", "Use a valid date in YYYY-MM-DD format.") from error
            if start > end:
                raise CopilotError("invalid_date_range", "The start date must be on or before the end date.")
            entities["date_range"] = {"start": start.isoformat(), "end": end.isoformat()}




def _apply_deterministic_entities(question, source, entities):
    """Extract security and schema-sensitive filters independently of the LLM."""
    lower = question.casefold()
    if (source == "employee" or re.search(r"\b(?:employee|attendance|by\s+(?:name|email))\b", lower)) and not re.search(r"\bsection\s+[a-z]\b", lower):
        email_match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", question, re.IGNORECASE)
        if email_match:
            entities["employee_email"] = email_match.group(0).casefold()
        else:
            identity = re.search(
                r"\b(?:employee named|named|for employee|employee|attendance for|for)\s+([A-Z][A-Z .'-]{1,60}?)(?=\s+(?:in|from|on|during|with|whose|today|yesterday|for the last|last 7 days)\b|[?.!,]|$)",
                question,
                re.IGNORECASE,
            )
            if identity:
                candidate = identity.group(1).strip()
                if candidate.casefold() not in {"name", "email", "name or email", "employee", "an employee"}:
                    entities["employee_name"] = candidate
        if re.search(r"\b(?:name or email|by name|by email|for employee|employee attendance|for name|for email)\b", lower) and not (entities.get("employee_email") or entities.get("employee_name")):
            if re.search(r"\bby\s+name\b", lower):
                raise CopilotError("clarification_required", "Please provide the employee's name.")
            if re.search(r"\bby\s+email\b", lower):
                raise CopilotError("clarification_required", "Please provide the employee's email address.")
            raise CopilotError("clarification_required", "Please provide the employee's name or email address.")
    if re.search(r"\bsection\s*(?:\?|$|today\b|yesterday\b)", lower) and not entities.get("section"):
        raise CopilotError("clarification_required", "Which section should I check?")
    if re.search(r"\bsub[- ]?section\s*(?:\?|$|today\b|yesterday\b)", lower) and not entities.get("subsection"):
        raise CopilotError("clarification_required", "Which subsection should I check?")
    if re.search(r"\bdepartment\s*(?:\?|$)", lower) and not entities.get("department"):
        raise CopilotError("clarification_required", "Which department should I check?")
    if re.search(r"\b(?:student department|department of students)\b", lower):
        entities["department"] = "__STUDENT_DEPARTMENT__"
    department_match = re.search(r"\b(?:in|for|from)\s+([A-Z][A-Z &'-]{1,60})\s+department\b", question, re.IGNORECASE)
    if department_match:
        entities["department"] = department_match.group(1).strip()
    status = re.search(r"\b(present|incomplete|on leave|leave|checked in|completed)\b", lower)
    if status:
        value = status.group(1)
        entities["attendance_status"] = {"on leave": "LEAVE", "leave": "LEAVE", "checked in": "INCOMPLETE", "completed": "PRESENT"}.get(value, value.upper())


def _validate_absence_date_range(entities):
    date_range = entities.get("date_range")
    if not date_range:
        raise CopilotError(
            "clarification_required",
            "Which past date should I check? Absence means an active employee has no attendance record and no approved leave for that date.",
        )
    if date_range["start"] != date_range["end"]:
        raise CopilotError(
            "unsupported_absence_range",
            "I can check absence for one past date at a time. Please give a single date.",
        )
    absence_date = date.fromisoformat(date_range["start"])
    if absence_date >= timezone.localdate():
        raise CopilotError(
            "incomplete_absence_period",
            "Absence can only be inferred for a completed past date.",
        )


def derive_scope(user):
    if user.is_superuser:
        return {"sections": None, "subsections": None, "unrestricted": True}
    sections = sorted({str(v).strip().upper() for v in (user.hr_copilot_sections or []) if str(v).strip()})
    subsections = sorted({str(v).strip().upper() for v in (user.hr_copilot_subsections or []) if str(v).strip()})
    if not sections and subsections:
        sections = sorted({v[0] for v in subsections if v})
    if not sections:
        raise CopilotError("scope_unassigned", "Your HR Copilot scope has not been assigned. Contact a Super Admin.", 403)
    return {"sections": sections, "subsections": subsections or None, "unrestricted": False}


def plan_query(intent, scope):
    if not intent["source"] or intent["intent"] == "unknown":
        raise CopilotError("unknown_question", "I don’t have enough information to answer that HR question.")
    entities = dict(intent["entities"])
    if entities.pop("employee_identity_missing", False):
        raise CopilotError("clarification_required", "Please provide the employee's name or email address.")
    employee_resolution = {"status": "not_required", "employee_id": None}
    if entities.get("employee_name") or entities.get("employee_email"):
        if entities.get("employee_email"):
            matches = Employee.objects.filter(user__email__iexact=entities["employee_email"])
        else:
            name_parts = entities["employee_name"].split()
            matches = Employee.objects.filter(user__first_name__iexact=name_parts[0], user__last_name__iexact=" ".join(name_parts[1:]))
        matching_ids = list(matches.values_list("id", flat=True)[:2])
        if not matching_ids:
            raise CopilotError("employee_not_found", "No employee matched that name or email.")
        if len(matching_ids) > 1:
            raise CopilotError("employee_ambiguous", "More than one employee matched. Please provide the employee's email address.")
        employee_resolution = {"status": "resolved", "employee_id": matching_ids[0]}
        entities["employee_id"] = matching_ids[0]
    if entities.get("department"):
        departments = set(Employee.objects.values_list("department", flat=True).distinct())
        requested_department = entities["department"]
        if requested_department == "__STUDENT_DEPARTMENT__":
            department = next((value for value in departments if value.casefold() in {"student", "student department"}), None)
        else:
            department = next((value for value in departments if value.casefold() == requested_department.casefold()), None)
        if department is None:
            message = "The employee data does not identify a Student Department category." if requested_department == "__STUDENT_DEPARTMENT__" else "That department is not present in the employee data."
            raise CopilotError("department_not_found", message)
        entities["department"] = department
    is_absence_query = intent["intent"].startswith("absence_")
    if is_absence_query:
        _validate_absence_date_range(entities)
    if intent["intent"] == "comparison" and len(entities.get("comparison_subsections", [])) < 2:
        raise CopilotError("clarification_required", "Which two sections or sub-sections should I compare?")
    section, subsection = entities.get("section"), entities.get("subsection")
    if not scope["unrestricted"]:
        if section and section not in scope["sections"]:
            raise CopilotError("scope_denied", "You don’t have access to the requested section.", 403)
        if subsection and (
            subsection[0] not in scope["sections"]
            or (scope["subsections"] and subsection not in scope["subsections"])
        ):
            raise CopilotError("scope_denied", "You don’t have access to the requested sub-section.", 403)
        compared = entities.get("comparison_subsections", [])
        if len(compared) > 10:
            raise CopilotError("invalid_intent", "Please compare no more than ten sub-sections.")
        if any(value[0] not in scope["sections"] or (scope["subsections"] and value not in scope["subsections"]) for value in compared):
            raise CopilotError("scope_denied", "You don’t have access to one or more requested sub-sections.", 403)
    if employee_resolution["status"] == "resolved" and not scope["unrestricted"]:
        employee = Employee.objects.filter(pk=employee_resolution["employee_id"]).only("section", "subsection").first()
        if employee.section not in scope["sections"] or (scope["subsections"] and employee.subsection not in scope["subsections"]):
            raise CopilotError("scope_denied", "You do not have access to that employee.", 403)
    return {
        "source": intent["source"], "intent": intent["intent"], "filters": entities,
        "scope": scope, "limit": MAX_ROWS, "employee": employee_resolution,
        "temporal_scope": entities.get("temporal_scope"),
        "aggregation": "count" if intent["intent"].endswith("count") else None,
    }


def build_sql(plan):
    source, filters, scope = plan["source"], plan["filters"], plan["scope"]
    intent = plan["intent"]
    is_absence_query = intent.startswith("absence_")
    params, where = [], []
    if scope["sections"] is not None:
        where.append("e.section IN (" + ", ".join(["%s"] * len(scope["sections"])) + ")")
        params.extend(scope["sections"])
    if scope["subsections"]:
        where.append("e.subsection IN (" + ", ".join(["%s"] * len(scope["subsections"])) + ")")
        params.extend(scope["subsections"])
    for key, column in (("section", "e.section"), ("subsection", "e.subsection"), ("employee_type", "e.employment_type")):
        if filters.get(key):
            where.append(column + " = %s")
            params.append(filters[key])
    if filters.get("employee_id"):
        where.append("e.id = %s")
        params.append(filters["employee_id"])
    if filters.get("employee_email"):
        where.append("u.email = %s")
        params.append(filters["employee_email"])
    if filters.get("department"):
        where.append("e.department = %s")
        params.append(filters["department"])
    if "is_active" in filters and source == "employee":
        where.append("e.is_active = %s")
        params.append(filters["is_active"])
    if filters.get("comparison_subsections"):
        values = filters["comparison_subsections"]
        where.append("e.subsection IN (" + ", ".join(["%s"] * len(values)) + ")")
        params.extend(values)

    if source == "employee":
        from_sql, date_field = "employees_employee e JOIN accounts_user u ON u.id = e.user_id", "e.date_joined"
    elif source == "attendance":
        from_sql = "attendance_attendance a JOIN employees_employee e ON e.id = a.employee_id JOIN accounts_user u ON u.id = e.user_id"
        date_field = "a.date"
        if filters.get("attendance_status"):
            where.append("a.status = %s")
            params.append(filters["attendance_status"])
    else:
        from_sql = "leave_management_leaverequest lr JOIN employees_employee e ON e.id = lr.employee_id JOIN accounts_user u ON u.id = e.user_id JOIN leave_management_leavetype lt ON lt.id = lr.leave_type_id"
        date_field = "lr.start_date"
        if filters.get("leave_status"):
            where.append("lr.status = %s")
            params.append(filters["leave_status"])
    if is_absence_query:
        absence_date = filters["date_range"]["start"]
        where.extend([
            "e.is_active = TRUE",
            "e.date_joined <= %s",
            "NOT EXISTS (SELECT 1 FROM attendance_attendance absent_attendance "
            "WHERE absent_attendance.employee_id = e.id AND absent_attendance.date = %s)",
            "NOT EXISTS (SELECT 1 FROM leave_management_leaverequest approved_leave "
            "WHERE approved_leave.employee_id = e.id AND approved_leave.status = 'APPROVED' "
            "AND approved_leave.start_date <= %s AND approved_leave.end_date >= %s)",
        ])
        params.extend([absence_date, absence_date, absence_date, absence_date])

    if filters.get("date_range") and not is_absence_query:
        where.extend([date_field + " >= %s", date_field + " <= %s"])
        params.extend([filters["date_range"]["start"], filters["date_range"]["end"]])
    if intent.endswith("count"):
        select_sql, group_sql = ("COUNT(DISTINCT e.id) AS value" if source == "employee" else "COUNT(*) AS value"), ""
    elif intent in ("employee_summary", "attendance_summary", "leave_summary", "comparison"):
        category = "a.status" if source == "attendance" else "lr.status" if source == "leave" else "e.employment_type"
        if intent == "comparison" and filters.get("comparison_subsections"):
            select_sql = "e.subsection AS scope, " + category + " AS category, COUNT(*) AS value"
            group_sql = " GROUP BY e.subsection, " + category + " ORDER BY e.subsection, value DESC"
        else:
            select_sql, group_sql = category + " AS category, COUNT(*) AS value", " GROUP BY " + category + " ORDER BY value DESC"
    elif intent.endswith("trend"):
        date_col = "a.date" if source == "attendance" else "lr.start_date" if source == "leave" else "e.date_joined"
        category = "a.status" if source == "attendance" else "lr.status" if source == "leave" else None
        select_sql = date_col + " AS date, " + ((category + " AS category, ") if category else "") + "COUNT(*) AS value"
        group_sql = " GROUP BY " + date_col + ((", " + category) if category else "") + " ORDER BY " + date_col + " ASC LIMIT %s"
        params.append(plan["limit"])
    elif source == "employee":
        select_sql = "e.id, u.first_name, u.last_name, u.email, e.department, e.employment_type, e.section, e.subsection, e.is_active, e.date_joined"
        group_sql = " ORDER BY u.last_name, u.first_name LIMIT %s"
        params.append(plan["limit"])
    elif source == "attendance":
        select_sql = "u.first_name, u.last_name, e.section, e.subsection, a.date, a.status, a.check_in, a.check_out, a.working_duration"
        group_sql = " ORDER BY a.date DESC LIMIT %s"
        params.append(plan["limit"])
    else:
        select_sql = "u.first_name, u.last_name, e.section, e.subsection, lt.name AS leave_type, lr.start_date, lr.end_date, lr.duration_days, lr.status, lr.reason"
        group_sql = " ORDER BY lr.submitted_at DESC LIMIT %s"
        params.append(plan["limit"])
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    return "SELECT " + select_sql + " FROM " + from_sql + where_sql + group_sql, params


def validate_sql(sql, plan=None):
    # In the request path, require the exact query text generated for the validated
    # plan. This also bounds columns and joins to the fixed templates above.
    if plan is not None and sql != build_sql(plan)[0]:
        raise CopilotError("sql_rejected", "The query does not match an approved query template.")
    statements = [item for item in sqlparse.parse(sql) if str(item).strip()]
    if len(statements) != 1 or statements[0].get_type() != "SELECT" or FORBIDDEN_SQL.search(sql):
        raise CopilotError("sql_rejected", "The query did not pass the read-only safety check.")
    tables = re.findall(r"\b(?:FROM|JOIN)\s+([a-z_][a-z0-9_]*)", sql, re.IGNORECASE)
    if not tables or any(table not in ALLOWED_TABLES for table in tables):
        raise CopilotError("sql_rejected", "The query uses a data source that is not allowed.")
    if re.search(r"\bSELECT\s+\*", sql, re.IGNORECASE):
        raise CopilotError("sql_rejected", "Wildcard column selection is not allowed.")
    limit = re.search(r"\bLIMIT\s+(\d+)\b", sql, re.IGNORECASE)
    if limit and int(limit.group(1)) > MAX_ROWS:
        raise CopilotError("sql_rejected", "The query exceeds the maximum result size.")
    return True


def execute_query(sql, params):
    from django.db import transaction

    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SET LOCAL statement_timeout = '5000ms'")
            cursor.execute(sql, params)
            columns = [item[0] for item in cursor.description]
            rows = cursor.fetchall()
    return columns, rows


def serialize_result(columns, rows):
    result = []
    for row in rows:
        entry = {}
        for key, value in zip(columns, row):
            if hasattr(value, "isoformat"):
                entry[key] = value.isoformat()
            elif value is None or isinstance(value, (str, int, float, bool)):
                entry[key] = value
            else:
                entry[key] = str(value)
        result.append(entry)
    return result


def generate_answer(intent, data):
    intent_name = intent.get("intent", "")
    if not data:
        if intent_name.startswith("absence_"):
            return "No absent employees were found for that date and authorized scope."
        if intent.get("entities", {}).get("is_active") is False:
            return "No inactive employees were found in your authorized scope."
        return "No matching HR records were found for your authorized scope and filters."
    if len(data) == 1 and "value" in data[0] and "category" not in data[0]:
        value = data[0]["value"]
        if intent_name == "absence_count":
            return str(value) + " employee" + (" was" if value == 1 else "s were") + " absent on that date."
        noun = "employee" if intent["source"] == "employee" else "record"
        return str(value) + " " + noun + ("" if value == 1 else "s") + " matched your question."
    if intent_name == "absence_lookup":
        return "I found " + str(len(data)) + " absent employee(s). See the data below for details."
    return "I found " + str(len(data)) + " result group(s). See the data below for details."
