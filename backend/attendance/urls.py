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
    KioskFaceCheckInView,
    KioskFaceCheckOutView,
    FaceVerifyView,
    WebsiteFacialCheckInView,
    WebsiteFacialCheckOutView,
)


urlpatterns = [
    path("check-in/", CheckInView.as_view(), name="check-in"),
    path("website-facial-check-in/", WebsiteFacialCheckInView.as_view(), name="website-facial-check-in"),
    path("website-facial-check-out/", WebsiteFacialCheckOutView.as_view(), name="website-facial-check-out"),
    path("check-out/", CheckOutView.as_view(), name="check-out"),
    path("today/", TodayAttendanceView.as_view(), name="today-attendance"),
    path("history/", AttendanceHistoryView.as_view(), name="attendance-history"),
    path("kiosk/check-in/", KioskFaceCheckInView.as_view(), name="kiosk-check-in"),
    path("kiosk/check-out/", KioskFaceCheckOutView.as_view(), name="kiosk-check-out"),
    path("verify-face/", FaceVerifyView.as_view(), name="verify-face"),
]