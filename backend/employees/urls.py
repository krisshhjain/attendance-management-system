from django.urls import path

from .views import EmployeeCreateView, EmployeeListView, EmployeeDetailView


urlpatterns = [
    path("", EmployeeCreateView.as_view(), name="employee-create"),
    path("list/", EmployeeListView.as_view(), name="employee-list"),
    path("<int:pk>/", EmployeeDetailView.as_view(), name="employee-detail"),
]