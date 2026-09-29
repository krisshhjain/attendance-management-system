from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import NotificationSerializer


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        notifications = Notification.objects.filter(user=request.user).select_related(
            "attendance_event"
        )

        unread = request.query_params.get("unread")
        if unread is not None and unread.lower() in {"1", "true", "yes"}:
            notifications = notifications.filter(is_read=False)

        notifications = notifications.order_by("-created_at", "-id")
        return Response(NotificationSerializer(notifications, many=True).data)


class NotificationReadView(APIView):
    permission_classes = [IsAuthenticated]

    def _mark_read(self, request, pk):
        notification = get_object_or_404(
            Notification,
            pk=pk,
            user=request.user,
        )
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read"])
        return Response(NotificationSerializer(notification).data)

    def post(self, request, pk):
        return self._mark_read(request, pk)

    def patch(self, request, pk):
        return self._mark_read(request, pk)


class NotificationDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        notification = get_object_or_404(
            Notification,
            pk=pk,
            user=request.user,
        )
        if notification.notification_type != "ATTENDANCE":
            return Response(
                {"detail": "Only transient attendance notifications can be deleted."},
                status=400,
            )
        notification.delete()
        return Response(status=204)
