"""Stable public JSON helpers for Copilot read and write responses.

``result_response`` and ``action_response`` describe the payload contract.
``safe_error_message`` maps selected internal codes to browser-safe text
so provider details are not returned.
"""


def result_response(
    *, answer, intent, data, scope=None, conversation_id=None, metadata=None
):
    """Construct a standard dictionary payload for successful read queries."""
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


def action_response(
    *,
    answer,
    intent,
    status,
    conversation_id=None,
    action_id=None,
    action_result=None,
    pending_action=None,
):
    """Construct a standard dictionary payload for write action states."""
    payload = {
        "response_type": (
            "action_success"
            if status == "executed"
            else (
                "action_preview"
                if status in {"pending_approval", "awaiting_information"}
                else "action_failure"
            )
        ),
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
        "llm_unavailable":
        "I couldn't interpret that request right now. Please try again.",
        "invalid_intent":
        "I couldn't determine a safe HR action from that request.",
        "normalization_failed":
        "I couldn't determine a safe HR action from that request.",
        "ungrounded_llm_response":
        "I couldn't verify that answer from the HR records.",
        "query_failed":
        "I couldn't complete that HR query. Please try a more specific "
            'question.',
    }.get(code, fallback)
