from django.urls import path

from .views import ActiveHolidayListView, HolidayAdminDetailView, HolidayAdminListCreateView


urlpatterns = [
    path("", ActiveHolidayListView.as_view(), name="active-holidays"),
    path("admin/", HolidayAdminListCreateView.as_view(), name="holiday-admin-list-create"),
    path("admin/<int:pk>/", HolidayAdminDetailView.as_view(), name="holiday-admin-detail"),
]
