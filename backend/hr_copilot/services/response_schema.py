"""Stable public response helpers for HR Copilot."""


def result_response(*, answer, intent, data, scope=None, conversation_id=None, metadata=None):
    payload = {
        "response_type": "result",
        "answer": answer,
        "intent": intent,
        "query_status": "executed",
        "conversation_id": conversation_id,
        "data": data,
    }
    if scope is not None:
        payload["scope"] = scope
    if metadata:
        payload["metadata"] = metadata
    return payload


def action_response(*, answer, intent, status, conversation_id=None, action_id=None, action_result=None, pending_action=None):
    payload = {
        "response_type": "action_success" if status == "executed" else "action_preview" if status in {"pending_approval", "awaiting_information"} else "action_failure",
        "answer": answer,
        "intent": intent,
        "query_status": status,
        "conversation_id": conversation_id,
        "action_id": action_id,
        "data": None,
    }
    if action_result is not None:
        payload["action_result"] = action_result
    if pending_action is not None:
        payload["pending_action"] = pending_action
    return payload


def safe_error_message(code, fallback):
    """Prevent provider/implementation details from reaching the browser."""
    return {
        "llm_unavailable": "I couldn't interpret that request right now. Please try again.",
        "invalid_intent": "I couldn't determine a safe HR action from that request.",
        "normalization_failed": "I couldn't determine a safe HR action from that request.",
        "ungrounded_llm_response": "I couldn't verify that answer from the HR records.",
        "query_failed": "I couldn't complete that HR query. Please try a more specific question.",
    }.get(code, fallback)
