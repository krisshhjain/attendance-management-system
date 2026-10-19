"""Application configuration for the HR Copilot Django app."""

from django.apps import AppConfig


class HrCopilotConfig(AppConfig):
    """Django app configuration for HR Copilot."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "hr_copilot"
