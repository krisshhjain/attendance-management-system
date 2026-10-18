"""
ASGI configuration for the Attendance Management System.

Exposes the ASGI callable as a module-level variable named `application`.
Used by asynchronous servers (e.g., Uvicorn, Daphne) to process asynchronous
HTTP and WebSocket traffic, setting the default Django settings module before
initializing the application handler.

For more information on this file, see:
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

# Ensure project settings are loaded before initializing the ASGI application callable
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_asgi_application()
