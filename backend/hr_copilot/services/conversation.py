"""Structured, authorization-safe context for HR Copilot follow-up questions."""

import re
import uuid
import json
from datetime import datetime, timezone as dt_timezone
from django.db import transaction

from ..models import CopilotConversationContext


FOLLOW_UP_REFERENCE = re.compile(r"\b(?:he|she|they|them|that employee|the employee)\b", re.IGNORECASE)


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
    """Apply conversation context using semantic understanding."""
    # The semantic interpreter now handles context application internally
    # This function remains for backward compatibility but delegates to the interpreter
    from .semantic_interpreter import semantic_interpreter
    
    # Re-interpret with context if we have conversation history
    if context:
        enhanced_intent = semantic_interpreter.interpret_query(question, context)
        return enhanced_intent
    
    return intent


def save_context(user, conversation_id, plan):
    if not conversation_id:
        return
    context = {
        "current_employee_id": plan.get("employee", {}).get("employee_id"),
        "current_section": plan.get("filters", {}).get("section"),
        "current_subsection": plan.get("filters", {}).get("subsection"),
        "current_date_context": plan.get("temporal_scope"),
        "last_intent": plan.get("intent"),
    }
    CopilotConversationContext.objects.update_or_create(
        user=user, conversation_id=conversation_id, defaults={"context": context},
    )
