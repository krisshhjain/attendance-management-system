import json
import re
from datetime import date

from .pipeline import CopilotError
from .providers import LLMProviderError, get_llm_provider
from .session_memory import session_memory
from .intent_normalizer import intent_normalizer


ALLOWED_INTENTS = {
    # Read operations (existing)
    "employee_lookup", "employee_count", "employee_summary",
    "attendance_lookup", "attendance_summary", "attendance_trend",
    "absence_lookup", "absence_count",
    "leave_lookup", "leave_summary", "leave_trend", "comparison", "unknown",
    # Write operations (new)
    "attendance_update", "attendance_create", "attendance_delete",
    "leave_create", "leave_update", "leave_cancel", "leave_approve", "leave_deny",
    "employee_update", "bulk_attendance_update",
}
ALLOWED_SOURCES = {"employee", "attendance", "leave", None}
ALLOWED_ENTITIES = {
    "section", "subsection", "comparison_subsections", "employee_type",
    "employee_name", "employee_email", "department", "is_active", "attendance_status", "leave_status", "date_range",
    "temporal_expression", "missing_information", "ambiguities", "operation_type",
    # Write operation entities (new)
    "action_type", "target_status", "reason", "duration_days", "leave_type", "bulk_target",
    "check_in_time", "check_out_time"
}
VALID_DATE_RANGE_KEYS = {"start", "end"}
FINAL_ANSWER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answer"],
    "properties": {"answer": {"type": "string", "minLength": 1, "maxLength": 800}},
}
INTENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["intent", "entities"],
    "properties": {
        "intent": {"type": "string", "enum": sorted(ALLOWED_INTENTS)},
        "entities": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "section": {"type": "string"},
                "subsection": {"type": "string"},
                "comparison_subsections": {"type": "array", "items": {"type": "string"}},
                "employee_type": {"type": "string"},
                "employee_name": {"type": "string"},
                "employee_email": {"type": "string"},
                "department": {"type": "string"},
                "is_active": {"type": "boolean"},
                "attendance_status": {"type": "string"},
                "leave_status": {"type": "string"},
                "temporal_expression": {"type": "string"},
                "missing_information": {"type": "array", "items": {"type": "string"}},
                "ambiguities": {"type": "array", "items": {"type": "string"}},
                "operation_type": {"type": "string", "enum": ["list", "count", "summary", "trend", "lookup"]},
                # Write operation entities
                "target_status": {"type": "string"},
                "reason": {"type": "string"},
                "duration_days": {"type": "number"},
                "leave_type": {"type": "string"},
                "bulk_target": {"type": "string", "enum": ["section", "subsection", "department"]},
                "check_in_time": {"type": "string"}, "check_out_time": {"type": "string"}
            },
        },
        "missing_information": {"type": "array", "items": {"type": "string"}},
        "ambiguities": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}


def get_structured_intent(question, session_id=None, context=None):
    try:
        provider = get_llm_provider()
    except LLMProviderError as error:
        raise CopilotError("llm_unavailable", "The local Qwen intent service is unavailable. Please try again.", 503) from error
    if provider is None:
        return None
    
    # Get compact session context if available
    session_context = {}
    if session_id:
        session_context = session_memory.get_compact_context(session_id)
    if context:
        session_context = {**session_context, **context}
    
    # Build compact system prompt - focus only on semantic understanding
    system_content = (
        "Extract HR semantic intent as JSON. Focus on WHAT the user wants, not backend implementation.\n"
        "Intents: attendance_lookup, attendance_update, employee_lookup, leave_lookup, leave_create, absence_lookup\n"
        "Use attendance_update when the user asks to mark/change an employee's attendance status to PRESENT, ABSENT, or LEAVE. Keep ABSENT distinct from LEAVE; only use LEAVE for an explicit leave status. Use leave_create only when they ask to submit/file a leave request.\n"
        "Partial write actions are valid: extract every known employee/date/action field even when time or reason is missing; leave missing fields absent and report them in missing_information.\n"
        "For attendance writes, recognize employee names after mark/make/set and extract dates such as 29th September, September 29, or numeric day/month/year.\n"
                "When a user says 'Mark [employee] as present for [date]', classify it as attendance_update with target_status PRESENT, preserving employee_name and date_range even when check-in and check-out are missing. For 'absent', use target_status ABSENT; for explicit 'on leave', use target_status LEAVE. Never substitute one for the other.\n"
        "Extract: intent, employee_name, employee_email, temporal_expression or date_range, target_status (for updates)\n"
        "For PRESENT attendance updates, also extract check_in_time and check_out_time when provided. For LEAVE attendance changes and leave requests, extract reason when provided.\n"
        "Write operations: 'mark as', 'set to', 'make', 'put on', 'create', 'update', 'change'\n"
        "Read operations: 'who was', 'show', 'list', 'when did', 'how many'\n"
        "Status values: 'absent', 'present', 'incomplete'\n"
    )
    
    # Add minimal context if available
    if session_context:
        context_str = json.dumps(session_context, separators=(',', ':'))
        system_content += f"Context: {context_str}\n"
    
    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": question},
    ]
    
    try:
        result = provider.structured_output(messages, schema=INTENT_SCHEMA, options={"num_predict": 128, "temperature": 0})
    except LLMProviderError as error:
        raise CopilotError("llm_unavailable", "The local Qwen intent service is unavailable. Please try again.", 503) from error

    if not isinstance(result, dict):
        raise CopilotError("invalid_intent", "The HR intent service returned an invalid response.", 503)
    
    # Normalize the LLM output using the intent normalizer
    try:
        normalized_intent = intent_normalizer.normalize_intent(result, question)
        intent_normalizer.validate_normalized_intent(normalized_intent)
    except CopilotError:
        # Re-raise CopilotErrors as-is
        raise
    except Exception as error:
        raise CopilotError("normalization_failed", "Failed to normalize intent from LLM output.", 503) from error
    # Apply legacy validation for backward compatibility (with normalized source)
    intent, source, entities = normalized_intent.get("intent"), normalized_intent.get("source"), normalized_intent.get("entities", {})
    if intent not in ALLOWED_INTENTS or source not in ALLOWED_SOURCES or not isinstance(entities, dict):
        raise CopilotError("invalid_intent", "The HR intent service returned an invalid response.", 503)
    
    # Entity validation is now handled by the normalizer, but keep legacy checks
    if set(entities.keys()) - ALLOWED_ENTITIES:
        raise CopilotError("invalid_intent", "The HR intent service returned unsupported filters.", 503)

    clean = {key: value for key, value in entities.items() if value is not None}
    # Validate additional fields if present
    for key in ("missing_information", "ambiguities"):
        if key in normalized_intent and not isinstance(normalized_intent[key], list):
            raise CopilotError("invalid_intent", f"The HR intent service returned invalid {key}.", 503)
    
    if "confidence" in normalized_intent and not isinstance(normalized_intent["confidence"], (int, float)):
        raise CopilotError("invalid_intent", "The HR intent service returned invalid confidence.", 503)
    if "date_range" in clean:
        value = clean["date_range"]
        if not isinstance(value, dict) or set(value) != VALID_DATE_RANGE_KEYS:
            raise CopilotError("invalid_intent", "The HR intent service returned an invalid date range.", 503)
        if any(not isinstance(value[side], str) or len(value[side]) != 10 for side in VALID_DATE_RANGE_KEYS):
            raise CopilotError("invalid_intent", "The HR intent service returned an invalid date range.", 503)
        try:
            start = date.fromisoformat(value["start"])
            end = date.fromisoformat(value["end"])
        except ValueError as error:
            raise CopilotError("invalid_intent", "The HR intent service returned an invalid date range.", 503) from error
        if start > end:
            raise CopilotError("invalid_intent", "The HR intent service returned an invalid date range.", 503)
    if "comparison_subsections" in clean:
        values = clean["comparison_subsections"]
        if not isinstance(values, list) or len(values) > 10 or any(not isinstance(value, str) or not re.fullmatch(r"[A-Za-z][0-9]+", value) for value in values):
            raise CopilotError("invalid_intent", "The HR intent service returned invalid comparison filters.", 503)
        clean["comparison_subsections"] = [value.upper() for value in values]
    if "section" in clean:
        clean["section"] = clean["section"].upper()
    if "subsection" in clean:
        clean["subsection"] = clean["subsection"].upper()
    for key, choices in (
        ("employee_type", {"PERMANENT", "CONTRACT", "INTERN"}),
        ("attendance_status", {"PRESENT", "INCOMPLETE", "LEAVE"}),
        ("leave_status", {"PENDING", "APPROVED", "DENIED", "CANCELLED"}),
    ):
        if key in clean and clean[key] not in choices:
            raise CopilotError("invalid_intent", "The HR intent service returned an unsupported filter.", 503)
    if "is_active" in clean and not isinstance(clean["is_active"], bool):
        raise CopilotError("invalid_intent", "The HR intent service returned an invalid employee status.", 503)
    
    # Update the normalized intent with cleaned entities
    normalized_intent["entities"] = clean
    
    # Store context from successful intent for future use
    if session_id:
        context_updates = session_memory.extract_context_from_intent(normalized_intent)
        context_updates["last_query"] = question
        session_memory.update_session_state(session_id, **context_updates)
    
    return normalized_intent


def extract_pending_action_fields(question, required_fields):
    """Use the configured intent provider to extract only fields for an active draft."""
    try:
        provider = get_llm_provider()
    except LLMProviderError as error:
        raise CopilotError("llm_unavailable", "The local intent service is unavailable. Please try again.", 503) from error
    fields = set(required_fields)
    if 'employee_name' in fields or 'employee_email' in fields:
        fields.update({'employee_name', 'employee_email'})
    schema = {
        "type": "object", "additionalProperties": False,
        "properties": {field: {"type": "string"} for field in fields},
    }
    messages = [
        {"role": "system", "content": "Extract only explicitly supplied values for the requested missing HR action fields. Do not infer missing values. For times, return 24-hour HH:MM; interpret a lone checkout hour from 1 through 11 as PM when it follows a morning check-in. Return an empty object if the message supplies none."},
        {"role": "user", "content": json.dumps({"missing_fields": required_fields, "reply": question})},
    ]
    try:
        result = provider.structured_output(messages, schema=schema, options={"num_predict": 96, "temperature": 0})
    except LLMProviderError as error:
        raise CopilotError("llm_unavailable", "The local intent service is unavailable. Please try again.", 503) from error
    if not isinstance(result, dict):
        raise CopilotError("invalid_intent", "The intent service returned an invalid follow-up response.", 503)
    return {key: value.strip() for key, value in result.items() if key in fields and isinstance(value, str) and value.strip()}


def generate_natural_answer(question, intent, data, session_id=None):
    """Ask local Qwen to phrase only the verified backend result, with deterministic fallback."""
    
    # First try deterministic response generation (no Qwen dependency)
    deterministic_answer = _generate_deterministic_answer(intent, data)
    if deterministic_answer:
        return deterministic_answer
    
    # If deterministic fails, try Qwen (but don't fail the entire request if Qwen is unavailable)
    try:
        provider = get_llm_provider()
    except LLMProviderError:
        # Qwen unavailable - return deterministic fallback
        return _generate_fallback_answer(intent, data)
    
    if provider is None:
        # Qwen not configured - return deterministic fallback
        return _generate_fallback_answer(intent, data)

    try:
        # Reduce data size - send only essential facts, not full records
        compact_data = _compact_result_data(data, intent)
        verified_result = json.dumps(compact_data, ensure_ascii=False, default=str, separators=(',', ':'))
        
        # Compact system prompt
        system_content = (
            "HR response writer. Return JSON with 'answer' key. "
            "Use ONLY facts in VERIFIED_RESULT. Repeat names/emails/numbers exactly. "
            "No pronouns - use verified names. No inferences beyond VERIFIED_RESULT. "
            "Empty result = 'No matching HR records found.'"
        )
        
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": f"Q: {question}\nINTENT: {intent['intent']}\nDATA: {verified_result}"},
        ]
        
        result = provider.structured_output(messages, schema=FINAL_ANSWER_SCHEMA, options={"num_predict": 96})
        answer = result.get("answer", "").strip() if isinstance(result, dict) else ""
        if not answer:
            # Qwen returned invalid response - use fallback
            return _generate_fallback_answer(intent, data)
        
        _validate_grounded_answer(answer, compact_data)
        return answer
        
    except (LLMProviderError, Exception):
        # Any Qwen error - return deterministic fallback
        return _generate_fallback_answer(intent, data)


def _generate_deterministic_answer(intent, data):
    """Generate deterministic responses for common cases without needing Qwen."""
    intent_name = intent.get("intent", "")
    
    # Handle empty results
    if not data:
        if intent_name.startswith("absence_"):
            return "No absent employees found for the specified criteria."
        elif intent.get("entities", {}).get("is_active") is False:
            return "No inactive employees found."
        else:
            return "No matching HR records found."
    
    # Handle count results
    if len(data) == 1 and "value" in data[0] and "category" not in data[0]:
        value = data[0]["value"]
        if intent_name == "absence_count":
            return f"{value} employee{'s' if value != 1 else ''} {'were' if value != 1 else 'was'} absent."
        elif intent_name.endswith("_count"):
            entity_type = intent_name.replace("_count", "").replace("_", " ")
            return f"{value} {entity_type} record{'s' if value != 1 else ''} found."
    
    # Handle single employee profile
    if intent.get("source") == "employee" and len(data) == 1:
        employee = data[0]
        name = f"{employee.get('first_name', '')} {employee.get('last_name', '')}".strip()
        if name and employee.get('department'):
            status = "active" if employee.get("is_active", True) else "inactive"
            return f"{name} is an {status} {employee.get('employment_type', 'employee').lower()} in {employee.get('department')}, Section {employee.get('section', '')}, Subsection {employee.get('subsection', '')}."
    
    # Handle single attendance record
    if intent.get("source") == "attendance" and len(data) == 1:
        record = data[0]
        name = f"{record.get('first_name', '')} {record.get('last_name', '')}".strip()
        if name and record.get('date') and record.get('status'):
            status = record['status'].replace('_', ' ').lower()
            return f"{name} was {status} on {record['date']}."
    
    # For other cases, return None to try Qwen or fallback
    return None


def _generate_fallback_answer(intent, data):
    """Generate fallback answer when both deterministic and Qwen fail."""
    if not data:
        return "No matching HR records found."
    
    count = len(data)
    intent_name = intent.get("intent", "")
    
    if intent_name.startswith("absence_"):
        return f"Found {count} absent employee{'s' if count != 1 else ''}."
    elif intent.get("source") == "employee":
        return f"Found {count} employee{'s' if count != 1 else ''}."
    elif intent.get("source") == "attendance":
        return f"Found {count} attendance record{'s' if count != 1 else ''}."
    elif intent.get("source") == "leave":
        return f"Found {count} leave record{'s' if count != 1 else ''}."
    else:
        return f"Found {count} HR record{'s' if count != 1 else ''}."


def _compact_result_data(data, intent):
    """Reduce result data size while preserving essential information."""
    if not data:
        return data
    
    # For count queries, just return the count
    if len(data) == 1 and "value" in data[0] and "category" not in data[0]:
        return data
    
    # For single employee profile, keep essential fields only
    if intent.get("source") == "employee" and len(data) == 1:
        employee = data[0]
        return [{
            "name": f"{employee.get('first_name', '')} {employee.get('last_name', '')}".strip(),
            "email": employee.get("email"),
            "department": employee.get("department"),
            "employment_type": employee.get("employment_type"),
            "section": employee.get("section"),
            "subsection": employee.get("subsection"),
            "is_active": employee.get("is_active"),
        }]
    
    # For attendance records, keep only essential fields
    if intent.get("source") == "attendance":
        return [{
            "first_name": row.get("first_name"),
            "last_name": row.get("last_name"),
            "date": row.get("date"),
            "status": row.get("status"),
        } for row in data[:10]]  # Limit to first 10 records
    
    # For leave records, keep essential fields
    if intent.get("source") == "leave":
        return [{
            "first_name": row.get("first_name"),
            "last_name": row.get("last_name"),
            "leave_type": row.get("leave_type"),
            "start_date": row.get("start_date"),
            "end_date": row.get("end_date"),
            "status": row.get("status"),
        } for row in data[:10]]  # Limit to first 10 records
    
    # For summary/count data, return as-is but limit entries
    if all("category" in row or "value" in row for row in data):
        return data[:20]  # Limit to first 20 summary entries
    
    # Default: return first 5 records with essential fields only
    essential_fields = ["first_name", "last_name", "email", "department", "section", "subsection", "date", "status", "value", "category"]
    return [{k: v for k, v in row.items() if k in essential_fields} for row in data[:5]]


def _validate_grounded_answer(answer, data):
    """Reject likely factual additions before a model response reaches the client."""
    if not data:
        answer_lower = answer.casefold()
        if not any(phrase in answer_lower for phrase in [
            "no matching", "no record", "no employee", "couldn't find", "could not find",
            "none found", "no absent", "no inactive", "not find any", "no attendance",
        ]):
            raise CopilotError("ungrounded_llm_response", "The local Qwen response could not be verified.", 503)
        return
    source = json.dumps(data, ensure_ascii=False, default=str).casefold()
    answer_words = set(re.findall(r"\b[a-z][a-z0-9@._+-]{2,}\b", answer.casefold()))
    answer_numbers = set(re.findall(r"\b\d+(?:[-.:/]\d+)*\b", answer))
    source_dates = set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", source))
    answer_dates = set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", answer))
    factual_words = {word for word in answer_words if word not in {
        "the", "and", "for", "with", "that", "there", "were", "was", "are", "from", "your", "has", "have",
        "matching", "records", "record", "found", "employee", "employees", "attendance", "leave", "result", "results",
        "no", "not", "this", "those", "today", "query", "requested", "within", "authorized", "scope", "is",
        "in", "on", "of", "as", "an", "all", "their", "they", "been", "including", "showing",
    }}
    unsupported = {word for word in factual_words if (any(char.isdigit() for char in word) or "@" in word) and word not in source}
    unsupported.update(
        value for value in answer_numbers
        if value not in source and value != str(len(data))
    )
    unsupported.update(value for value in answer_dates if value not in source_dates)
    capitalized = set(re.findall(r"\b[A-Z][a-z]{2,}\b", answer))
    permitted_capitalized = {
        "The", "There", "No", "I", "Here", "For", "Your", "This", "These", "That", "Those",
        "He", "She", "They", "It", "Section", "Subsection", "Department", "Status", "Date",
        "Active", "Inactive", "Present", "Absent", "Leave", "Permanent", "Contract", "Intern",
        "As", "An", "A", "In", "On", "At", "By", "With", "From", "To", "And", "Or", "Currently",
        "All", "Any", "Both", "Each", "Total", "Count", "Summary", "Details", "Records", "Record",
        "Employee", "Employees", "Attendance", "Yes", "None", "She", "He", "Joined",
    }
    unsupported.update(
        word.casefold() for word in capitalized
        if word not in permitted_capitalized and word.casefold() not in source
    )
    if unsupported:
        raise CopilotError("ungrounded_llm_response", "The local Qwen response could not be verified.", 503)
