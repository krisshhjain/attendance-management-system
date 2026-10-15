from unittest.mock import patch

from django.db import OperationalError
from django.test import RequestFactory, SimpleTestCase

from .health import health_check


class HealthCheckTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get("/healthz/")

    @patch("config.health.connection.ensure_connection")
    def test_returns_ready_when_database_is_available(self, ensure_connection):
        response = health_check(self.request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
        ensure_connection.assert_called_once_with()

    @patch(
        "config.health.connection.ensure_connection",
        side_effect=OperationalError("database unavailable"),
    )
    def test_returns_unavailable_when_database_is_down(
        self, _ensure_connection
    ):
        response = health_check(self.request)

        self.assertEqual(response.status_code, 503)
