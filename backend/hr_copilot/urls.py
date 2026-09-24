from django.urls import path

from .views import HRCopilotQueryView

urlpatterns = [
    path("query/", HRCopilotQueryView.as_view(), name="hr-copilot-query"),
]
