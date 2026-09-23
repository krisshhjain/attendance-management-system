from django.urls import path

from .views import AdminAttendanceView, AdminForceCheckoutView


urlpatterns = [
    path("attendance/", AdminAttendanceView.as_view(), name="admin-attendance"),
    path("force-checkout/", AdminForceCheckoutView.as_view(), name="admin-force-checkout"),
]