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