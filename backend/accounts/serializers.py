from django.contrib.auth import password_validation
from rest_framework import serializers


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
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
    email = serializers.EmailField()
    is_staff = serializers.BooleanField()
    is_superuser = serializers.BooleanField()
    must_change_password = serializers.SerializerMethodField()

    def get_must_change_password(self, obj):
        try:
            return obj.employee.must_change_password
        except Exception:
            return False
