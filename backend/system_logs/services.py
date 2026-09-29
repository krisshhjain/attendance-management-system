import re
from collections.abc import Mapping
from datetime import date, datetime, time
from decimal import Decimal
from uuid import UUID

from django.db import models

from .models import SystemLog


SYSTEM_ACTOR = "SYSTEM"
MAX_DEPTH = 5
MAX_ITEMS = 50
MAX_STRING_LENGTH = 2048

_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?:password|passwd|passphrase|token|secret|api[_-]?key|authorization|cookie|"
    r"csrf|refresh|access[_-]?token|private[_-]?key|face|biometric|embedding|template)",
    re.IGNORECASE,
)
_SECRET_VALUE_PATTERNS = (
    re.compile(r"^Bearer\s+\S+$", re.IGNORECASE),
    re.compile(r"^eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$"),
    re.compile(r"^-----BEGIN [A-Z ]+-----"),
)


def record_event(
    *,
    event_type,
    category,
    severity,
    status,
    actor=None,
    target=None,
    message="",
    source="",
    request=None,
    request_id=None,
    before_state=None,
    after_state=None,
    metadata=None,
):
    """Create one sanitized, append-only system log record."""
    actor_obj, actor_role = _resolve_actor(actor)
    target_fields = _serialize_target(target)
    request_values = _request_values(request)

    resolved_request_id = request_id or request_values["request_id"]
    return SystemLog.objects.create(
        event_type=_bounded_string(event_type),
        category=_bounded_string(category),
        severity=_bounded_string(severity),
        status=_bounded_string(status),
        actor=actor_obj,
        actor_role=actor_role,
        target_type=target_fields["target_type"],
        target_id=target_fields["target_id"],
        target_label=target_fields["target_label"],
        message=_sanitize_string(message),
        source=_bounded_string(source),
        ip_address=request_values["ip_address"],
        user_agent=request_values["user_agent"],
        request_id=_bounded_string(resolved_request_id),
        before_state=_sanitize_json(before_state),
        after_state=_sanitize_json(after_state),
        metadata=_sanitize_json(metadata or {}),
    )


def _resolve_actor(actor):
    if actor is None:
        return None, "ANONYMOUS"
    if isinstance(actor, str) and actor.upper() == SYSTEM_ACTOR:
        return None, SYSTEM_ACTOR

    if not getattr(actor, "is_authenticated", True):
        return None, "ANONYMOUS"
    if getattr(actor, "is_superuser", False):
        return actor, "SUPERUSER"
    if getattr(actor, "is_system_admin", False):
        return actor, "MANAGER"
    if _has_employee(actor):
        return actor, "EMPLOYEE"
    if getattr(actor, "is_staff", False):
        return actor, "STAFF"
    return actor, "USER"


def _has_employee(actor):
    try:
        return actor.employee is not None
    except (AttributeError, models.ObjectDoesNotExist):
        return False


def _serialize_target(target):
    empty = {"target_type": "", "target_id": "", "target_label": ""}
    if target is None:
        return empty

    if isinstance(target, Mapping):
        target_type = target.get("target_type", target.get("type", ""))
        target_id = target.get("target_id", target.get("id", ""))
        target_label = target.get(
            "target_label",
            target.get("label", target.get("name", "")),
        )
        return {
            "target_type": _bounded_string(target_type),
            "target_id": _bounded_string(target_id),
            "target_label": _sanitize_string(target_label),
        }

    if isinstance(target, models.Model):
        return {
            "target_type": _bounded_string(target._meta.label_lower),
            "target_id": _bounded_string(target.pk),
            "target_label": _sanitize_string(str(target)),
        }

    target_label = _sanitize_string(target)
    return {
        "target_type": _bounded_string(type(target).__name__),
        "target_id": target_label,
        "target_label": target_label,
    }


def _request_values(request):
    values = {"ip_address": None, "user_agent": "", "request_id": ""}
    if request is None:
        return values

    meta = getattr(request, "META", {}) or {}
    values["ip_address"] = meta.get("REMOTE_ADDR")
    values["user_agent"] = _sanitize_string(meta.get("HTTP_USER_AGENT", ""))
    values["request_id"] = _bounded_string(
        getattr(request, "request_id", "") or meta.get("HTTP_X_REQUEST_ID", "")
    )
    return values


def _sanitize_json(value, depth=0):
    if depth >= MAX_DEPTH:
        return "[TRUNCATED]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _sanitize_string(value)
    if isinstance(value, (datetime, date, time, UUID, Decimal)):
        return _bounded_string(value.isoformat() if hasattr(value, "isoformat") else value)
    if isinstance(value, Mapping):
        sanitized = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= MAX_ITEMS:
                sanitized["[TRUNCATED_ITEMS]"] = True
                break
            safe_key = _bounded_string(key)
            sanitized[safe_key] = (
                "[REDACTED]"
                if _SENSITIVE_KEY_PATTERN.search(safe_key)
                else _sanitize_json(item, depth + 1)
            )
        return sanitized
    if isinstance(value, (list, tuple, set)):
        items = [_sanitize_json(item, depth + 1) for item in list(value)[:MAX_ITEMS]]
        if len(value) > MAX_ITEMS:
            items.append("[TRUNCATED_ITEMS]")
        return items
    return _sanitize_string(str(value))


def _sanitize_string(value):
    safe_value = _bounded_string(value)
    if any(pattern.search(safe_value) for pattern in _SECRET_VALUE_PATTERNS):
        return "[REDACTED]"
    return safe_value


def _bounded_string(value):
    if value is None:
        return ""
    return str(value)[:MAX_STRING_LENGTH]
