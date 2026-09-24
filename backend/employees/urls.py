from django.urls import path

from .views import EmployeeCreateView, EmployeeListView, EmployeeDetailView, AdminEmployeePasswordChangeView, EmployeeFaceEnrollmentView


urlpatterns = [
    path("", EmployeeCreateView.as_view(), name="employee-create"),
    path("list/", EmployeeListView.as_view(), name="employee-list"),
    path("<int:pk>/", EmployeeDetailView.as_view(), name="employee-detail"),
    path("<int:pk>/change-password/", AdminEmployeePasswordChangeView.as_view(), name="employee-change-password"),
    path("<int:pk>/enroll-face/", EmployeeFaceEnrollmentView.as_view(), name="employee-enroll-face"),
]