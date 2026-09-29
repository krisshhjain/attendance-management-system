from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class SystemLog(models.Model):
    SEVERITY_CHOICES = [
        ("DEBUG", "Debug"),
        ("INFO", "Info"),
        ("WARNING", "Warning"),
        ("ERROR", "Error"),
        ("CRITICAL", "Critical"),
    ]

    STATUS_CHOICES = [
        ("SUCCESS", "Success"),
        ("FAILED", "Failed"),
        ("DENIED", "Denied"),
        ("PENDING", "Pending"),
        ("RETRY", "Retry"),
        ("CANCELLED", "Cancelled"),
        ("SKIPPED", "Skipped"),
    ]

    timestamp = models.DateTimeField(default=timezone.now, editable=False)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    category = models.CharField(max_length=32)
    event_type = models.CharField(max_length=64)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="system_logs",
    )
    actor_role = models.CharField(max_length=20)
    target_type = models.CharField(max_length=128, blank=True, default="")
    target_id = models.CharField(max_length=128, blank=True, default="")
    target_label = models.CharField(max_length=255, blank=True, default="")
    message = models.TextField()
    source = models.CharField(max_length=32)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    request_id = models.CharField(max_length=128, blank=True, default="")
    before_state = models.JSONField(null=True, blank=True)
    after_state = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        ordering = ["-timestamp", "-id"]
        indexes = [
            models.Index(fields=["timestamp", "id"], name="system_log_time_idx"),
            models.Index(fields=["event_type", "timestamp", "id"], name="system_log_event_idx"),
            models.Index(fields=["category", "timestamp", "id"], name="system_log_category_idx"),
            models.Index(fields=["severity", "timestamp", "id"], name="system_log_severity_idx"),
            models.Index(fields=["status", "timestamp", "id"], name="system_log_status_idx"),
            models.Index(fields=["actor", "timestamp", "id"], name="system_log_actor_idx"),
            models.Index(fields=["request_id"], name="system_log_request_idx"),
            models.Index(
                fields=["target_type", "target_id", "timestamp"],
                name="system_log_target_idx",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("SystemLog records are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("SystemLog records are immutable.")

    def __str__(self):
        return f"{self.timestamp} {self.event_type} ({self.status})"
