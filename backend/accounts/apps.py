"""
Application configuration for the accounts module.
"""
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """
    Configuration class for the accounts app, establishing the 64-bit integer
    primary key default and application namespace.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
