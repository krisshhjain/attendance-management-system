from django.urls import path
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
    MyTeamView,
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
    path("my-team/", MyTeamView.as_view(), name="my-team"),
]