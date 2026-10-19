from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    attendance_event_type = serializers.CharField(
        source="attendance_event.event_type",
        read_only=True,
        allow_null=True,
    )
    attendance_event_timestamp = serializers.DateTimeField(
        source="attendance_event.timestamp",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = Notification
        fields = [
            "id",
            "title",
            "message",
            "notification_type",
            "is_read",
            "created_at",
            "attendance_event",
            "attendance_event_type",
            "attendance_event_timestamp",
        ]
        read_only_fields = fields
