from django.urls import path

from .views import (
    AdminAttendanceView,
    AdminForceCheckoutView,
    AdminResetAttendanceView,
    AdminEditAttendanceView
)


urlpatterns = [
    path("attendance/", AdminAttendanceView.as_view(), name="admin-attendance"),
    path("force-checkout/", AdminForceCheckoutView.as_view(), name="admin-force-checkout"),
    path("attendance/reset/", AdminResetAttendanceView.as_view(), name="admin-attendance-reset"),
    path("attendance/edit/", AdminEditAttendanceView.as_view(), name="admin-attendance-edit"),
]