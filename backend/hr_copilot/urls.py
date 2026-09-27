from django.urls import path

from .views import HRCopilotHealthView, HRCopilotQueryView, HRCopilotActionApprovalView, HRCopilotPendingActionsView

urlpatterns = [
    path("health/", HRCopilotHealthView.as_view(), name="hr-copilot-health"),
    path("query/", HRCopilotQueryView.as_view(), name="hr-copilot-query"),
    path("actions/approve/", HRCopilotActionApprovalView.as_view(), name="hr-copilot-action-approval"),
    path("actions/pending/", HRCopilotPendingActionsView.as_view(), name="hr-copilot-pending-actions"),
]
