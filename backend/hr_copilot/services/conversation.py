"""Structured, authorization-safe context for HR Copilot follow-up questions."""

import re

from ..models import CopilotConversationContext


FOLLOW_UP_REFERENCE = re.compile(r"\b(?:he|she|they|them|that employee|the employee)\b", re.IGNORECASE)


def load_context(user, conversation_id):
    if not conversation_id:
        return {}
    record = CopilotConversationContext.objects.filter(user=user, conversation_id=conversation_id).only("context").first()
    return dict(record.context) if record else {}


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
