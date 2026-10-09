"""Small helpers for fail-closed secret configuration."""

from django.core.exceptions import ImproperlyConfigured


def required_secret(environment, name):
    """Return a configured secret or fail without exposing its value."""
    value = environment.get(name, "")
    if not isinstance(value, str) or not value.strip():
        raise ImproperlyConfigured(
            f"{name} must be configured in the environment before Django starts."
        )
    return value


def validate_production_configuration(
    environment,
    debug,
    allowed_hosts,
    database_password,
    broker_url,
    llm_provider="",
    llm_url="",
    email_backend="",
):
    """Reject development-only settings when explicitly running in production."""
    if environment != "production":
        return
    if debug:
        raise ImproperlyConfigured("DJANGO_DEBUG must be false in production")
    if not allowed_hosts or "*" in allowed_hosts:
        raise ImproperlyConfigured("ALLOWED_HOSTS must list production hostnames")
    if database_password == "attendance_password":
        raise ImproperlyConfigured("POSTGRES_PASSWORD must be set to a production secret")
    if "guest:guest@" in broker_url or "attendance_password" in broker_url:
        raise ImproperlyConfigured("CELERY_BROKER_URL must use production credentials")
    if llm_provider == "local_ollama_qwen" or "localhost" in llm_url or "127.0.0.1" in llm_url:
        raise ImproperlyConfigured("Local LLM configuration is not allowed in production")
    if email_backend.endswith("console.EmailBackend"):
        raise ImproperlyConfigured("Console email backend is not allowed in production")
