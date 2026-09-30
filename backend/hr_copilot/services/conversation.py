"""Structured, authorization-safe context for HR Copilot follow-up questions."""

import re
import uuid
import json
from datetime import datetime, timezone as dt_timezone
from django.db import transaction

from ..models import CopilotConversationContext


FOLLOW_UP_REFERENCE = re.compile(r"\b(?:he|she|they|them|his|her|their|that employee|the employee|that request|that leave|it)\b", re.IGNORECASE)


def load_context(user, conversation_id):
    if not conversation_id:
        return {}
    record = CopilotConversationContext.objects.filter(user=user, conversation_id=conversation_id).only("context").first()
    return dict(record.context) if record else {}


def append_message(user, conversation_id, role, content, metadata=None):
    """Persist a chat turn server-side so route changes and reloads can restore it."""
    if not conversation_id:
        return
    with transaction.atomic():
        CopilotConversationContext.objects.get_or_create(user=user, conversation_id=conversation_id)
        record = CopilotConversationContext.objects.select_for_update().get(user=user, conversation_id=conversation_id)
        messages = list(record.messages or [])
        item = {
            "id": str(uuid.uuid4()),
            "role": role,
            "content": str(content)[:4000],
            "timestamp": datetime.now(dt_timezone.utc).isoformat(),
        }
        if metadata:
            item.update(json.loads(json.dumps(metadata, default=lambda value: value.isoformat() if hasattr(value, 'isoformat') else str(value))))
        messages.append(item)
        record.messages = messages[-200:]
        record.save(update_fields=["messages", "updated_at"])


def load_messages(user, conversation_id):
    if not conversation_id:
        return []
    record = CopilotConversationContext.objects.filter(
        user=user, conversation_id=conversation_id,
    ).only("messages").first()
    return list(record.messages or []) if record else []


def update_action_message(user, conversation_id, action_id, status, content=None):
    if not conversation_id:
        return
    with transaction.atomic():
        record = CopilotConversationContext.objects.select_for_update().filter(user=user, conversation_id=conversation_id).first()
        if not record:
            return
        changed = False
        messages = list(record.messages or [])
        for message in messages:
            pending = message.get('pending_action')
            if pending and str(pending.get('action_id')) == str(action_id):
                pending['status'] = status
                if content:
                    message['content'] = content
                changed = True
        if changed:
            record.messages = messages
            record.save(update_fields=['messages', 'updated_at'])


def apply_context(question, intent, context):
    """Apply follow-up facts without spending a second LLM call.

    ``SemanticInterpreter`` already applies context during the initial intent
    extraction. Re-interpreting here doubled latency and allowed a small model
    to turn pronouns such as ``she`` into employee names. This final pass only
    copies safe, explicit facts into the already-normalized intent.
    """
    if not context:
        return intent

    result = dict(intent)
    entities = dict(intent.get("entities") or {})
    current_employee_id = context.get("current_employee_id")
    explicit_email = re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", question or "", re.IGNORECASE)

    if current_employee_id and not explicit_email and entities.get("employee_name"):
        current_name = str(context.get("current_employee_name") or "").casefold().strip()
        requested_name = str(entities["employee_name"]).casefold().strip()
        if requested_name and (requested_name == current_name or requested_name in current_name.split()):
            entities["employee_id"] = current_employee_id
            entities.pop("employee_name", None)
    if (
        current_employee_id
        and not any(entities.get(key) for key in ("employee_id", "employee_name", "employee_email"))
        and (
            FOLLOW_UP_REFERENCE.search(question)
            or (
                context.get("last_intent")
                and not re.search(r"\b(?:who|which employees|all employees|everyone|department|section|subsection)\b", question, re.IGNORECASE)
                and re.search(r"\b(?:attendance|worked|hours|incomplete|check.?in|check.?out|leave|regulari[sz]|balance|details?)\b", question, re.IGNORECASE)
            )
        )
    ):
        entities["employee_id"] = current_employee_id

    if (
        context.get("current_request_id")
        and not entities.get("request_id")
        and re.search(r"\b(?:that|this|the)\s+(?:leave\s+)?request\b|\bthat leave\b", question, re.IGNORECASE)
    ):
        entities["request_id"] = context["current_request_id"]

    if (
        not entities.get("temporal_expression")
        and re.search(r"\b(?:what about|how about)\s+(?:yesterday|today|last week|this month)\b", question, re.IGNORECASE)
    ):
        match = re.search(r"\b(yesterday|today|last week|this month)\b", question, re.IGNORECASE)
        if match:
            entities["temporal_expression"] = match.group(1).lower()

    if (
        not entities.get("date_range") and not entities.get("temporal_expression")
        and context.get("current_date") and context.get("current_date_end") and context.get("last_intent")
    ):
            entities["date_range"] = {
                "start": context["current_date"],
                "end": context["current_date_end"],
            }

    if (
        not entities.get("section")
        and context.get("current_section")
        and re.search(r"\b(?:what about|how about|only the|just the)\b", question, re.IGNORECASE)
        and not re.search(r"\b(?:section|department|employee)\b", question, re.IGNORECASE)
    ):
        entities["section"] = context["current_section"]

    result["entities"] = entities
    return result


def save_context(user, conversation_id, plan, data=None):
    if not conversation_id:
        return
    try:
        existing = load_context(user, conversation_id)
    except (AttributeError, TypeError):
        # Keep this helper usable with lightweight stores in unit tests.
        existing = {}
    context = {
        **existing,
        "current_employee_id": plan.get("employee", {}).get("employee_id") or existing.get("current_employee_id"),
        "current_section": plan.get("filters", {}).get("section") or existing.get("current_section"),
        "current_subsection": plan.get("filters", {}).get("subsection") or existing.get("current_subsection"),
        "current_date_context": plan.get("temporal_scope") or existing.get("current_date_context"),
        "last_intent": plan.get("intent") or existing.get("last_intent"),
        "current_metric": plan.get("attendance_metric") or plan.get("intelligence_metric") or plan.get("workforce_metric") or existing.get("current_metric"),
    }
    employee_id = context.get("current_employee_id")
    if employee_id and not context.get("current_employee_name"):
        try:
            from employees.models import Employee
            employee = Employee.objects.select_related("user").filter(pk=employee_id).first()
            if employee:
                context["current_employee_name"] = employee.user.get_full_name().strip() or employee.user.email
                context["current_employee_email"] = employee.user.email
        except Exception:
            # Lightweight context tests and non-database stores may not have
            # an Employee table; the employee ID remains safe to persist.
            pass
    if plan.get("filters", {}).get("date_range"):
        date_range = plan["filters"]["date_range"]
        context["current_date"] = date_range.get("start")
        context["current_date_end"] = date_range.get("end")
    if data and len(data) == 1:
        row = data[0]
        request_id = row.get("id") if row.get("leave_type") or row.get("request_type") else None
        if request_id:
            context["current_request_id"] = request_id
            context["current_request_type"] = "leave" if row.get("leave_type") else "regularization"
    if plan.get("current_request_id"):
        context["current_request_id"] = plan["current_request_id"]
    context = {key: value for key, value in context.items() if value is not None}
    CopilotConversationContext.objects.update_or_create(
        user=user, conversation_id=conversation_id, defaults={"context": context},
    )
