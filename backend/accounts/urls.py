"""
URL routing configuration for the accounts application.

These patterns are included by the root URL configuration under the
'api/auth/' prefix. Provides endpoints for login, token refresh,
password updates, and current user profile inspection.
"""

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import ChangePasswordView, LoginView, MeView, SystemAdminLoginView


urlpatterns = [
    # POST: Authenticate with email/password and obtain JWT access/refresh token pair
    path("login/", LoginView.as_view(), name="login"),

    # POST: Authenticate a system administrator
    path(
        "systemadmin-login/",
        SystemAdminLoginView.as_view(),
        name="systemadmin-login",
    ),

    # POST: Refresh expired access token using valid refresh token
    path("refresh/", TokenRefreshView.as_view(), name="token-refresh"),

    # POST: Authenticated password change and mandatory change flag reset
    path(
        "change-password/",
        ChangePasswordView.as_view(),
        name="change-password",
    ),

    # GET: Retrieve current authenticated user profile details
    path("me/", MeView.as_view(), name="me"),
]