from django.urls import path
from .views import (
    AdminApproveLeaveView,
    AdminCancelApprovedLeaveView,
    AdminDenyLeaveView,
    AdminEmployeeLeaveBalancesView,
    AdminLeaveRequestDetailView,
    AdminLeaveRequestsView,
    EmployeeCancelLeaveRequestView,
    EmployeeLeaveBalancesView,
    EmployeeLeaveRequestDetailView,
    EmployeeLeaveRequestsView,
    EmployeeLeaveTypesView,
    EstimateLeaveDurationView,
    FileUploadView,
    SuperAdminLeavePoliciesListCreateView,
    SuperAdminLeavePolicyDetailView,
    SuperAdminLeaveTypeDetailView,
    SuperAdminLeaveTypesListCreateView,
)

urlpatterns = [
    # Employee endpoints
    path("types/", EmployeeLeaveTypesView.as_view(), name="leave-types"),
    path("balances/", EmployeeLeaveBalancesView.as_view(), name="leave-balances"),
    path("requests/", EmployeeLeaveRequestsView.as_view(), name="leave-requests"),
    path("requests/<int:pk>/", EmployeeLeaveRequestDetailView.as_view(), name="leave-request-detail"),
    path("requests/<int:pk>/cancel/", EmployeeCancelLeaveRequestView.as_view(), name="leave-request-cancel"),
    path("estimate-duration/", EstimateLeaveDurationView.as_view(), name="leave-estimate-duration"),
    path("upload/", FileUploadView.as_view(), name="file-upload"),

    # Admin endpoints
    path("admin/requests/", AdminLeaveRequestsView.as_view(), name="admin-leave-requests"),
    path("admin/requests/<int:pk>/", AdminLeaveRequestDetailView.as_view(), name="admin-leave-request-detail"),
    path("admin/requests/<int:pk>/approve/", AdminApproveLeaveView.as_view(), name="admin-leave-approve"),
    path("admin/requests/<int:pk>/deny/", AdminDenyLeaveView.as_view(), name="admin-leave-deny"),
    path("admin/requests/<int:pk>/cancel/", AdminCancelApprovedLeaveView.as_view(), name="admin-leave-cancel"),
    path("admin/balances/", AdminEmployeeLeaveBalancesView.as_view(), name="admin-leave-balances"),

    # Super Admin endpoints
    path("admin/types/", SuperAdminLeaveTypesListCreateView.as_view(), name="admin-leave-types"),
    path("admin/types/<int:pk>/", SuperAdminLeaveTypeDetailView.as_view(), name="admin-leave-type-detail"),
    path("admin/policies/", SuperAdminLeavePoliciesListCreateView.as_view(), name="admin-leave-policies"),
    path("admin/policies/<int:pk>/", SuperAdminLeavePolicyDetailView.as_view(), name="admin-leave-policy-detail"),
]
