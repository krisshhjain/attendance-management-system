import json
import os
import re
from datetime import date
from urllib.error import URLError
from urllib.request import Request, urlopen

from .pipeline import CopilotError


ALLOWED_INTENTS = {
    "employee_lookup", "employee_count", "employee_summary",
    "attendance_lookup", "attendance_summary", "attendance_trend",
    "absence_lookup", "absence_count",
    "leave_lookup", "leave_summary", "leave_trend", "comparison", "unknown",
}
ALLOWED_SOURCES = {"employee", "attendance", "leave", None}
ALLOWED_ENTITIES = {
    "section", "subsection", "comparison_subsections", "employee_type",
    "employee_name", "employee_email", "department", "is_active", "attendance_status", "leave_status", "date_range",
}
VALID_DATE_RANGE_KEYS = {"start", "end"}


def get_structured_intent(question):
    base_url = os.environ.get("HR_COPILOT_LLM_URL", "").strip()
    if not base_url:
        return None
    model = os.environ.get("HR_COPILOT_LLM_MODEL", "qwen3:8b")
    endpoint = base_url if base_url.endswith("/api/chat") else base_url.rstrip("/") + "/api/chat"
    request_data = {
        "model": model,
        "stream": False,
        "format": "json",
        "messages": [
            {
                "role": "system",
                "content": (
                    "Extract a structured intent from the user question. Never generate SQL. "
                    "Return only JSON with keys intent, source, entities. "
                    "Allowed intents: " + ", ".join(sorted(ALLOWED_INTENTS)) + ". "
                    "Allowed source: employee, attendance, leave, or null. "
                    "Allowed entity keys: section, subsection, comparison_subsections, employee_type, "
                    "employee_name, employee_email, department, is_active, attendance_status, leave_status, date_range. "
                    "Do not invent entities. Use null or omit unknown values. date_range must be an object "
                    "with ISO YYYY-MM-DD start and end, or null. Absence means an active employee has no attendance "
                    "record and no approved leave covering the requested completed past date. Use only schema-supported facts."
                ),
            },
            {"role": "user", "content": question},
        ],
        "options": {"temperature": 0},
    }
    request = Request(
        endpoint,
        data=json.dumps(request_data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            outer = json.loads(response.read().decode("utf-8"))
        raw = outer.get("message", {}).get("content", "")
        result = json.loads(raw)
    except (URLError, TimeoutError, ValueError, KeyError, AttributeError) as error:
        raise CopilotError("llm_unavailable", "The HR intent service is unavailable. Please try again.", 503) from error

    if not isinstance(result, dict) or set(result) - {"intent", "source", "entities"}:
        raise CopilotError("invalid_intent", "The HR intent service returned an invalid response.", 503)
    intent, source, entities = result.get("intent"), result.get("source"), result.get("entities", {})
    if intent not in ALLOWED_INTENTS or source not in ALLOWED_SOURCES or not isinstance(entities, dict):
        raise CopilotError("invalid_intent", "The HR intent service returned an invalid response.", 503)
    expected_source = "employee" if intent.startswith(("employee_", "absence_")) else "attendance" if intent.startswith("attendance_") else "leave" if intent.startswith("leave_") else source
    if expected_source != source or (intent == "unknown" and source is not None):
        raise CopilotError("invalid_intent", "The HR intent service returned inconsistent intent data.", 503)
    if set(entities) - ALLOWED_ENTITIES:
        raise CopilotError("invalid_intent", "The HR intent service returned unsupported filters.", 503)

    clean = {key: value for key, value in entities.items() if value is not None}
    for key in ("section", "subsection", "employee_name", "employee_email", "department"):
        if key in clean and (not isinstance(clean[key], str) or len(clean[key]) > 100):
            raise CopilotError("invalid_intent", "The HR intent service returned invalid entities.", 503)
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
    return {"intent": intent, "source": source, "entities": clean}
