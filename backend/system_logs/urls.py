from django.urls import path

from .views import SystemLogActorView, SystemLogDetailView, SystemLogExportView, SystemLogListView


urlpatterns = [
    path("actors/", SystemLogActorView.as_view(), name="system-log-actors"),
    path("export/", SystemLogExportView.as_view(), name="system-log-export"),
    path("", SystemLogListView.as_view(), name="system-log-list"),
    path("<int:pk>/", SystemLogDetailView.as_view(), name="system-log-detail"),
]
