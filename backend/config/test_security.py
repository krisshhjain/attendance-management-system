from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.security import required_secret, validate_production_configuration


class RequiredSecretTests(SimpleTestCase):
    def test_returns_configured_persistent_secret(self):
        self.assertEqual(
            required_secret({"DJANGO_SECRET_KEY": "stable-test-value"}, "DJANGO_SECRET_KEY"),
            "stable-test-value",
        )

    def test_missing_secret_fails_closed_in_production(self):
        with self.assertRaisesMessage(
            ImproperlyConfigured, "DJANGO_SECRET_KEY must be configured"
        ):
            required_secret({"DJANGO_ENV": "production"}, "DJANGO_SECRET_KEY")

    def test_blank_secret_fails_closed(self):
        with self.assertRaises(ImproperlyConfigured):
            required_secret({"DJANGO_SECRET_KEY": "   "}, "DJANGO_SECRET_KEY")


class ProductionConfigurationTests(SimpleTestCase):
    def test_rejects_debug_wildcard_hosts_and_development_credentials(self):
        cases = [
            (True, ["example.com"], "strong", "amqp://broker", "remote", "https://llm", "smtp"),
            (False, ["*"], "strong", "amqp://broker", "remote", "https://llm", "smtp"),
            (False, ["example.com"], "attendance_password", "amqp://broker", "remote", "https://llm", "smtp"),
            (False, ["example.com"], "strong", "amqp://guest:guest@broker", "remote", "https://llm", "smtp"),
            (False, ["example.com"], "strong", "amqp://broker", "local_ollama_qwen", "http://127.0.0.1:11434", "smtp"),
            (False, ["example.com"], "strong", "amqp://broker", "remote", "https://llm", "django.core.mail.backends.console.EmailBackend"),
        ]
        for debug, hosts, db_password, broker, provider, llm_url, email_backend in cases:
            with self.subTest(debug=debug, hosts=hosts, db_password=db_password):
                with self.assertRaises(ImproperlyConfigured):
                    validate_production_configuration(
                        "production", debug, hosts, db_password, broker,
                        provider, llm_url, email_backend,
                    )

    def test_allows_secure_production_configuration(self):
        validate_production_configuration(
            "production", False, ["attendance.example.com"], "strong-secret",
            "amqps://worker:strong-secret@broker", "remote", "https://llm.example.com",
            "django.core.mail.backends.smtp.EmailBackend",
        )
