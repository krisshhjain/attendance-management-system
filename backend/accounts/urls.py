from django.urls import path

from rest_framework_simplejwt.views import TokenRefreshView

from .views import ChangePasswordView, LoginView, MeView, SystemAdminLoginView


urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("systemadmin-login/", SystemAdminLoginView.as_view(), name="systemadmin-login"),
    path("refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("me/", MeView.as_view(), name="me"),
]
