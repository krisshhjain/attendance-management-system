import re
from datetime import date, timedelta

import sqlparse
from django.db import connection
from django.utils import timezone
from employees.models import Employee

from .employee_resolver import employee_resolver

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


def analyze_question(question, context=None, session_id=None):
    """Extract semantic intent from natural language using enhanced LLM interpretation."""
    from .semantic_interpreter import semantic_interpreter
    from .write_actions import write_action_planner
    
    # Use semantic interpreter for all queries including absence and write actions
    intent = semantic_interpreter.interpret_query(question, context or {}, session_id=session_id)
    
    # Check if this is a write action requiring approval
    if write_action_planner.is_write_action(intent):
        intent['requires_approval'] = True
        intent['action_type'] = 'write'
    else:
        intent['action_type'] = 'read'
    
    # Handle missing information and ambiguities
    missing_info = intent.get("missing_information", [])
    ambiguities = intent.get("ambiguities", [])
    
    if ambiguities:
        if "employee_identity" in ambiguities:
            raise CopilotError("employee_ambiguous", "More than one employee matched. Please provide the employee's email address.")
        # Add other ambiguity handling as needed
    
    if missing_info:
        if "employee_identity" in missing_info:
            raise CopilotError("employee_not_found", "No employee matched that name or email.")
        elif "department" in missing_info:
            raise CopilotError("department_not_found", "That department is not present in the employee data.")
        # Add other missing information handling as needed
    
    # Apply temporal scope metadata for compatibility
    entities = intent.get("entities", {})
    if entities.get("date_range"):
        start, end = entities["date_range"]["start"], entities["date_range"]["end"]
        today = timezone.localdate()
        scope_type = "date" if start == end else "range"
        if start == today.isoformat():
            scope_type = "today"
        elif start == (today - timedelta(days=1)).isoformat() and end == start:
            scope_type = "yesterday"
        entities["temporal_scope"] = {"type": scope_type, "start_date": start, "end_date": end, "source": "llm_resolved"}
    
    # Validate absence date range if it's an absence query
    if intent.get("intent", "").startswith("absence_"):
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


MONTH_NAMES = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "june": 6, "jun": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10,
    "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def _parse_natural_date_string(text, today):
    lower = text.casefold()
    m1 = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]+)(?:\s+(\d{4}))?\b", lower)
    if m1 and m1.group(2) in MONTH_NAMES:
        day = int(m1.group(1))
        month = MONTH_NAMES[m1.group(2)]
        year = int(m1.group(3)) if m1.group(3) else today.year
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            pass
    m2 = re.search(r"\b([a-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s+(\d{4}))?\b", lower)
    if m2 and m2.group(1) in MONTH_NAMES:
        month = MONTH_NAMES[m2.group(1)]
        day = int(m2.group(2))
        year = int(m2.group(3)) if m2.group(3) else today.year
        try:
            return date(year, month, day).isoformat()
        except ValueError:
            pass
    return None


def _apply_explicit_date_range(question, entities, today):
    lower = question.casefold()
    if "the day before" in lower or "two days ago" in lower:
        value = (today - timedelta(days=2)).isoformat()
        entities["date_range"] = {"start": value, "end": value}
    elif "yesterday" in lower:
        value = (today - timedelta(days=1)).isoformat()
        entities["date_range"] = {"start": value, "end": value}
    elif re.search(r"\btoday\b", lower):
        value = today.isoformat()
        entities["date_range"] = {"start": value, "end": value}
    elif "last week" in lower or "last 7 days" in lower:
        entities["date_range"] = {"start": (today - timedelta(days=6)).isoformat(), "end": today.isoformat()}
    elif "this week" in lower:
        start = today - timedelta(days=today.weekday())
        entities["date_range"] = {"start": start.isoformat(), "end": today.isoformat()}
    elif "this month" in lower:
        entities["date_range"] = {"start": today.replace(day=1).isoformat(), "end": today.isoformat()}
    elif "last month" in lower:
        end = today.replace(day=1) - timedelta(days=1)
        entities["date_range"] = {"start": date(end.year, end.month, 1).isoformat(), "end": end.isoformat()}
    else:
        natural_date = _parse_natural_date_string(lower, today)
        if natural_date:
            entities["date_range"] = {"start": natural_date, "end": natural_date}
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
    if "comparison_subsections" not in entities:
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
    if (source == "employee" or re.search(r"\b(?:employee|attendance|present|absent|check.?in|check.?out|by\s+(?:name|email)|who|about|profile)\b", lower)) and not re.search(r"\bsection\s+[a-z]\b", lower):
        email_match = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", question, re.IGNORECASE)
        if email_match:
            entities["employee_email"] = email_match.group(0).casefold()
        else:
            identity = re.search(
                r"\b(?:employee named|named|for employee|employee|attendance for|for|about|who is|who's|tell me about|profile of|profile for)\s+([A-Z][A-Z .'-]{1,60}?)(?=\s+(?:present|absent|in|from|on|during|with|whose|today|yesterday|for the last|last 7 days)\b|[?.!,]|$)",
                question,
                re.IGNORECASE,
            )
            if identity:
                candidate = identity.group(1).strip()
                if candidate.casefold() not in {"name", "email", "name or email", "employee", "an employee"}:
                    entities["employee_name"] = candidate
            if "employee_name" not in entities:
                name_match = re.search(r"\b([A-Z][a-z]{1,30}(?:\s+[A-Z][a-z]{1,30})+)\b", question)
                if name_match:
                    candidate = name_match.group(1).strip()
                    # Strip leading sentence-starting words that are not part of a name
                    _non_name_starters = {
                        "was", "is", "did", "who", "what", "which", "show", "give",
                        "tell", "list", "find", "get", "fetch", "display", "can", "does",
                        "has", "have", "had", "will", "would", "could", "should", "shall",
                    }
                    parts = candidate.split()
                    while parts and parts[0].casefold() in _non_name_starters:
                        parts = parts[1:]
                    candidate = " ".join(parts)
                    if candidate and candidate.casefold() not in {
                        "student department", "ai intern", "section c", "section a", "section b", "section d",
                    }:
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
    if entities.get("employee_id"):
        employee_resolution = employee_resolver.resolve_employee(employee_id=entities["employee_id"]).as_dict()
        if employee_resolution["status"] != "resolved":
            raise CopilotError("employee_not_found", "No employee matched that identity.")
        entities["employee_id"] = employee_resolution["employee_id"]
    elif entities.get("employee_name") or entities.get("employee_email"):
        employee_resolution = employee_resolver.resolve_employee(
            name=entities.get("employee_name"), email=entities.get("employee_email"),
        ).as_dict()
        if employee_resolution["status"] == "not_found":
            raise CopilotError("employee_not_found", "No employee matched that name or email.")
        if employee_resolution["status"] == "ambiguous":
            raise CopilotError("employee_ambiguous", "More than one employee matched. Please provide the employee's email address.")
        entities["employee_id"] = employee_resolution["employee_id"]
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
    if intent["intent"] == "attendance_intelligence" and not entities.get("attendance_metric"):
        raise CopilotError("clarification_required", "Which attendance metric should I calculate?")
    if intent["intent"] == "leave_regularization_intelligence" and not entities.get("intelligence_metric"):
        raise CopilotError("clarification_required", "Which leave or regularization information should I retrieve?")
    if intent["intent"] == "workforce_intelligence" and not entities.get("workforce_metric"):
        raise CopilotError("clarification_required", "Which workforce information should I retrieve?")
    if intent["intent"] == "workforce_intelligence" and entities.get("workforce_metric") == "shift_assignments":
        # An employee-specific assignment query must resolve a target before
        # execution; otherwise the tool returns scoped employee assignments,
        # never the unrelated shift configuration list.
        if entities.get("employee_name") or entities.get("employee_email"):
            if employee_resolution["status"] != "resolved":
                raise CopilotError("employee_not_found", "No employee matched that name or email.")
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
        "attendance_metric": entities.get("attendance_metric"),
        "intelligence_metric": entities.get("intelligence_metric"),
        "workforce_metric": entities.get("workforce_metric"),
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
            "WHERE absent_attendance.employee_id = e.id AND absent_attendance.date = %s AND absent_attendance.status <> 'ABSENT')",
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
    if intent.get("source") == "employee" and len(data) == 1 and "name" in data[0]:
        employee = data[0]
        status = "active" if employee["is_active"] else "inactive"
        article = "an" if status == "active" else "an"
        return f"{employee['name']} is {article} {status} {employee['employment_type'].lower()} employee in {employee['department']}, Section {employee['section']}, Subsection {employee['subsection']}."
    if intent.get("source") == "attendance" and len(data) == 1 and (
        intent.get("entities", {}).get("employee_id") or intent.get("entities", {}).get("employee_name") or intent.get("entities", {}).get("employee_email")
    ):
        row = data[0]
        name = " ".join(part for part in [row.get("first_name", ""), row.get("last_name", "")] if part).strip() or "The employee"
        att_date = row.get("date", "that date")
        att_status = str(row.get("status", "")).replace("_", " ").capitalize()
        return f"{name} was {att_status} on {att_date}."
    if intent_name == "absence_lookup":
        return "I found " + str(len(data)) + " absent employee(s). See the data below for details."
    return "I found " + str(len(data)) + " result group(s). See the data below for details."
