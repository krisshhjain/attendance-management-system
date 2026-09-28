from django.conf import settings
from django.db import models
from django.db.models import Q


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=50, default="GENERAL")
    attendance_event = models.ForeignKey(
        "attendance.AttendanceEvent",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "attendance_event"],
                condition=Q(attendance_event__isnull=False),
                name="unique_notification_per_user_attendance_event",
            ),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} - {self.title}"
