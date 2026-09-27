from django.conf import settings
from django.db import models
from django.contrib.postgres.fields import ArrayField


DEFAULT_APP_ACCESS = {
    "dashboard": True,
    "attendance": True,
    "leave": True,
}


def default_app_access():
    return DEFAULT_APP_ACCESS.copy()


class Employee(models.Model):
    EMPLOYMENT_TYPES = [
        ("PERMANENT", "Permanent"),
        ("CONTRACT", "Contract"),
        ("INTERN", "Intern"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee",
    )
    department = models.CharField(max_length=100)
    employment_type = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_TYPES,
    )
    date_joined = models.DateField()
    is_active = models.BooleanField(default=True)
    must_change_password = models.BooleanField(default=True)
    section = models.CharField(max_length=10, blank=True, default="")
    subsection = models.CharField(max_length=10, blank=True, default="")
    app_access = models.JSONField(default=default_app_access, blank=True)
    shift = models.ForeignKey(
        "attendance.Shift",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
    )

    def __str__(self):
        return self.user.email
    
    def get_effective_shift(self):
        """
        Get the effective shift for this employee based on employment type configuration.
        
        Returns:
            - Employee's assigned shift if they have one (Employee.shift)
            - Single configured shift if exactly one exists for their employment type
            - None otherwise (no shifts configured or multiple shifts available)
        """
        # If employee has an explicitly assigned shift, use that
        if self.shift is not None:
            return self.shift
        
        # Check shifts configured for this employment type
        from attendance.models import Shift
        configured_shifts = Shift.objects.filter(
            employment_type=self.employment_type,
            is_active=True
        )
        
        # If exactly one shift configured, auto-assign it
        if configured_shifts.count() == 1:
            return configured_shifts.first()
        
        # Otherwise (0 or multiple), no effective shift
        return None

class FaceProfile(models.Model):
    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("INACTIVE", "Inactive"),
        ("FAILED", "Failed"),
    ]

    employee = models.OneToOneField(
        Employee, 
        on_delete=models.CASCADE, 
        related_name="face_profile"
    )
    face_template = ArrayField(models.FloatField(), size=512)
    model_name = models.CharField(max_length=50, default="ArcFace")
    detector_backend = models.CharField(max_length=50, default="retinaface")
    version = models.CharField(max_length=20, default="1.0")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"FaceProfile for {self.employee.user.email}"
