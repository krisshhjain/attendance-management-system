"""
User models and custom manager for the accounts application.

Implements an email-based custom User model replacing Django's default
username-based authentication.
"""
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """
    Custom manager for User where email is the unique identifier for
    authentication instead of a username.
    """

    def create_user(self, email, password=None, **extra_fields):
        """
        Create and save a standard User with the given email and password.

        Normalizes the email address and hashes the plaintext password via
        set_password() before persisting.
        """
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and save a SuperUser with staff and superuser privileges.

        Ensures is_staff, is_superuser, and is_active default to True
        for administrative access.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        return self.create_user(
            email=email,
            password=password,
            **extra_fields,
        )


class User(AbstractUser):
    """
    Custom User model using email as the unique login credential.

    Removes the default `username` field. The linked employee profile (if any)
    is accessible via the reverse one-to-one relation `user.employee`.
    """
    username = None
    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    # REQUIRED_FIELDS is empty so createsuperuser prompts only for email and password
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email
