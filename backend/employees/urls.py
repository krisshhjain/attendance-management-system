from django.urls import path

from .views import (
    EmployeeCreateView, 
    EmployeeListView, 
    EmployeeDetailView, 
    AdminEmployeePasswordChangeView, 
    EmployeeFaceEnrollmentView,
    ManagerCreateView,
    ManagerListView,
    ManagerDetailView,
    ManagerPasswordChangeView,
)


urlpatterns = [
    path("", EmployeeCreateView.as_view(), name="employee-create"),
    path("list/", EmployeeListView.as_view(), name="employee-list"),
    path("<int:pk>/", EmployeeDetailView.as_view(), name="employee-detail"),
    path("<int:pk>/change-password/", AdminEmployeePasswordChangeView.as_view(), name="employee-change-password"),
    path("<int:pk>/enroll-face/", EmployeeFaceEnrollmentView.as_view(), name="employee-enroll-face"),
    
    # Manager management (SuperUser only)
    path("managers/", ManagerCreateView.as_view(), name="manager-create"),
    path("managers/list/", ManagerListView.as_view(), name="manager-list"),
    path("managers/<int:pk>/", ManagerDetailView.as_view(), name="manager-detail"),
    path("managers/<int:pk>/change-password/", ManagerPasswordChangeView.as_view(), name="manager-change-password"),
]