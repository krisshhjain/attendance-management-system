"""
Serializers for user authentication and profile endpoints.

Provides validation logic for credential changes and serializes identity
and role flags for the authenticated user session.
"""
from django.contrib.auth import password_validation
from rest_framework import serializers


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for password change requests.

    Expects the authenticated user to supply their existing password and a new
    password meeting the project's password validation criteria.
    Both fields are write-only to prevent credential leakage in API responses.
    """
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        """
        Validate current password correctness and new password complexity.

        Requires 'request' in serializer context to reference the authenticated user.
        Raises ValidationError if the current password does not match or if the
        new password fails configured AUTH_PASSWORD_VALIDATORS.
        """
        user = self.context["request"].user

        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError({
                "current_password": "Current password is incorrect."
            })

        password_validation.validate_password(
            attrs["new_password"],
            user,
        )

        return attrs


class UserProfileSerializer(serializers.Serializer):
    """
    Serializer representing the authenticated user's profile and permissions.

    Exposes core identity flags (staff, superuser) and the forced password
    reset status sourced from the related Employee record.
    """
    email = serializers.EmailField()
    is_staff = serializers.BooleanField()
    is_superuser = serializers.BooleanField()
    must_change_password = serializers.SerializerMethodField()

    def get_must_change_password(self, obj):
        """
        Retrieve the password reset requirement flag from the linked employee.

        Returns False if the user has no linked Employee record (e.g., standard
        superusers or administrative accounts provisioned outside the employee flow).
        """
        try:
            return obj.employee.must_change_password
        except Exception:
            return False
