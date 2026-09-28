from django.urls import path

from .views import NotificationDeleteView, NotificationListView, NotificationReadView


urlpatterns = [
    path("", NotificationListView.as_view(), name="notification-list"),
    path("<int:pk>/", NotificationDeleteView.as_view(), name="notification-delete"),
    path("<int:pk>/read/", NotificationReadView.as_view(), name="notification-read"),
]
