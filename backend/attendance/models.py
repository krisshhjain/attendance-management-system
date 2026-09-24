from django.conf import settings
from django.db import models


class Attendance(models.Model):
    STATUS_CHOICES = [
        ("PRESENT", "Present"),
        ("INCOMPLETE", "Incomplete"),
        ("LEAVE", "Leave"),
    ]

    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    date = models.DateField()
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="INCOMPLETE",
    )
    leave_request = models.ForeignKey(
        "leave_management.LeaveRequest",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attendance_records",
    )
    working_duration = models.DurationField(null=True, blank=True)
    check_in_latitude = models.FloatField(null=True, blank=True)
    check_in_longitude = models.FloatField(null=True, blank=True)
    check_in_accuracy = models.FloatField(null=True, blank=True)
    check_in_distance = models.FloatField(null=True, blank=True)
    check_out_latitude = models.FloatField(null=True, blank=True)
    check_out_longitude = models.FloatField(null=True, blank=True)
    check_out_accuracy = models.FloatField(null=True, blank=True)
    check_out_distance = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "date"],
                name="unique_employee_attendance_per_day",
            )
        ]
        ordering = ["-date", "-check_in"]

    def __str__(self):
        return f"{self.employee} - {self.date}"


class AttendanceAuditLog(models.Model):
    EVENT_TYPES = [
        ("CHECK_IN", "Check In"),
        ("CHECK_OUT", "Check Out"),
        ("ENROLLMENT", "Enrollment"),
    ]
    STATUS_CHOICES = [
        ("SUCCESS", "Success"),
        ("FAILED_NO_FACE", "Failed - No Face"),
        ("FAILED_MULTI_FACE", "Failed - Multiple Faces"),
        ("FAILED_UNKNOWN", "Failed - Unknown Identity"),
        ("FAILED_ERROR", "Failed - Error"),
    ]

    timestamp = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    distance = models.FloatField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")
    # Optional: we could add a snapshot ImageField here in the future
    
    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.event_type} - {self.status} at {self.timestamp}"