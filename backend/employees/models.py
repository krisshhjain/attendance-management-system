from django.conf import settings
from django.db import models
from django.contrib.postgres.fields import ArrayField


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
    def __str__(self):
        return self.user.email

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