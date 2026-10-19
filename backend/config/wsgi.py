"""
WSGI configuration for the Attendance Management System.

Exposes the WSGI callable as a module-level variable named `application`.
Used by synchronous WSGI application servers (e.g., Gunicorn, uWSGI, mod_wsgi)
in production environments, ensuring the settings module is bound before
instantiating the WSGI application handler.

For more information on this file, see:
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# Ensure project settings are loaded before initializing the WSGI application callable
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()