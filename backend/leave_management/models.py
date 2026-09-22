from django.conf import settings
from django.db import models


class LeaveType(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, default="")
    is_active = models.BooleanField(default=True)
    is_paid = models.BooleanField(default=True)
    requires_document = models.BooleanField(default=False)
    allow_half_day = models.BooleanField(default=True)
    allow_past_dates = models.BooleanField(default=True)
    allow_future_dates = models.BooleanField(default=True)
    min_notice_days = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class LeavePolicy(models.Model):
    EMPLOYMENT_TYPES = [
        ("PERMANENT", "Permanent"),
        ("CONTRACT", "Contract"),
        ("INTERN", "Intern"),
    ]

    employee_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPES)
    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.CASCADE,
        related_name="policies",
    )
    annual_entitlement = models.DecimalField(max_digits=5, decimal_places=1, default=0.0)
    allow_carry_forward = models.BooleanField(default=False)
    max_carry_forward = models.DecimalField(max_digits=5, decimal_places=1, default=0.0)
    unused_expires = models.BooleanField(default=True)
    max_consecutive_days = models.IntegerField(default=10)
    min_notice_days = models.IntegerField(default=0)
    allow_half_day = models.BooleanField(default=True)
    requires_document = models.BooleanField(default=False)
    effective_from = models.DateField()
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-effective_from", "employee_type", "leave_type__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee_type", "leave_type", "effective_from"],
                name="unique_policy_per_employee_type_leave_type_effective_from",
            )
        ]

    def __str__(self):
        return f"{self.employee_type} - {self.leave_type.name} (from {self.effective_from})"


class LeaveRequest(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("DENIED", "Denied"),
        ("CANCELLED", "Cancelled"),
    ]

    DAY_TYPE_CHOICES = [
        ("FULL_DAY", "Full Day"),
        ("FIRST_HALF", "First Half"),
        ("SECOND_HALF", "Second Half"),
    ]

    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.CASCADE,
        related_name="leave_requests",
    )
    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.PROTECT,
        related_name="requests",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    day_type = models.CharField(
        max_length=20,
        choices=DAY_TYPE_CHOICES,
        default="FULL_DAY",
    )
    duration_days = models.DecimalField(max_digits=5, decimal_places=1)
    reason = models.TextField()
    attachment = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING",
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_leaves",
    )
    reviewer_remarks = models.TextField(blank=True, default="")
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cancelled_leaves",
    )

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.employee.user.email} - {self.leave_type.code} ({self.start_date} to {self.end_date}) [{self.status}]"
