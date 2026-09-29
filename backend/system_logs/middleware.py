import uuid

from .services import record_event


class RequestContextMiddleware:
    """Attach a request ID and record meaningful API security responses."""

    REQUEST_ID_HEADER = "HTTP_X_REQUEST_ID"
    RESPONSE_ID_HEADER = "X-Request-ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = self._request_id(request)
        response = self.get_response(request)

        if request.path.startswith("/api/") and response.status_code in (401, 403):
            event_type = (
                "UNAUTHORIZED_ACCESS"
                if response.status_code == 401
                else "FORBIDDEN_ACCESS"
            )
            record_event(
                event_type=event_type,
                category="SECURITY",
                severity="WARNING",
                status="DENIED",
                actor=getattr(request, "user", None),
                message=f"API request denied with HTTP {response.status_code}.",
                source="API",
                request=request,
                metadata={
                    "path": request.path,
                    "method": request.method,
                    "response_status": response.status_code,
                },
            )

        response[self.RESPONSE_ID_HEADER] = request.request_id
        return response

    @classmethod
    def _request_id(cls, request):
        supplied = request.META.get(cls.REQUEST_ID_HEADER, "")
        try:
            return str(uuid.UUID(supplied))
        except (ValueError, AttributeError, TypeError):
            return str(uuid.uuid4())
