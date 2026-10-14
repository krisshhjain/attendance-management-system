"""Minimal application readiness endpoint for container orchestration."""

from django.db import DatabaseError, connection
from django.http import HttpResponse
from django.views.decorators.http import require_GET


@require_GET
def health_check(_request):
    """Return ready only when the application can reach its database."""
    try:
        connection.ensure_connection()
    except DatabaseError:
        return HttpResponse(status=503)
    return HttpResponse("ok", content_type="text/plain")
