from django.urls import path
from .views import AdminDashboardView

from .views import (
    AdminAttendanceView,
    AdminDashboardView,
    AttendanceHistoryView,
    TodayAttendanceView,
    CheckInView,
    CheckOutView,
    AdminForceCheckoutView,
)


urlpatterns = [
    path("check-in/", CheckInView.as_view(), name="check-in"),
    path("check-out/", CheckOutView.as_view(), name="check-out"),
    path("today/", TodayAttendanceView.as_view(), name="today-attendance"),
    path("history/", AttendanceHistoryView.as_view(), name="attendance-history"),
]