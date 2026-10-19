import uuid


class RequestContextMiddleware:
    """Attach a request ID to each response."""

    REQUEST_ID_HEADER = "HTTP_X_REQUEST_ID"
    RESPONSE_ID_HEADER = "X-Request-ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = self._request_id(request)
        response = self.get_response(request)

        response[self.RESPONSE_ID_HEADER] = request.request_id
        return response

    @classmethod
    def _request_id(cls, request):
        supplied = request.META.get(cls.REQUEST_ID_HEADER, "")
        try:
            return str(uuid.UUID(supplied))
        except (ValueError, AttributeError, TypeError):
            return str(uuid.uuid4())
