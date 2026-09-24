from django.conf import settings
from django.db import models


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

    def __str__(self):
        return self.user.email
