from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        return self.create_user(
            email=email,
            password=password,
            **extra_fields,
        )


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    is_system_admin = models.BooleanField(default=False)
    hr_copilot_sections = models.JSONField(default=list, blank=True)
    hr_copilot_subsections = models.JSONField(default=list, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email


class ManagerScope(models.Model):
    SECTION = "SECTION"
    DEPARTMENT = "DEPARTMENT"
    SCOPE_TYPES = (
        (SECTION, "Section"),
        (DEPARTMENT, "Department"),
    )

    manager = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="manager_scopes",
    )
    scope_type = models.CharField(max_length=20, choices=SCOPE_TYPES)
    value = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("manager", "scope_type", "value"),
                name="unique_manager_scope_value",
            ),
        ]
        ordering = ("scope_type", "value", "id")

    def __str__(self):
        return f"{self.manager.email}: {self.scope_type}={self.value}"
