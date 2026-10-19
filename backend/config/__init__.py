"""
Core Django configuration package for the Attendance Management System.

Contains project-wide settings, URL routing, WSGI and ASGI entrypoints.
"""

from .celery import app as celery_app

__all__ = ["celery_app"]