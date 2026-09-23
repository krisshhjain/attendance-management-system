from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Employee


User = get_user_model()


class EmployeeCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    department = serializers.CharField(max_length=100)
    employment_type = serializers.ChoiceField(
        choices=Employee.EMPLOYMENT_TYPES
    )
    date_joined = serializers.DateField()
    section = serializers.CharField(max_length=10, required=False, allow_blank=True, default="")
    subsection = serializers.CharField(max_length=10, required=False, allow_blank=True, default="")

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "A user with this email already exists."
            )
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        email = validated_data.pop("email")
        first_name = validated_data.pop("first_name", "")
        last_name = validated_data.pop("last_name", "")

        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )

        return Employee.objects.create(
            user=user,
            must_change_password=True,
            **validated_data,
        )


class EmployeeUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    department = serializers.CharField(max_length=100, required=False)
    employment_type = serializers.ChoiceField(choices=Employee.EMPLOYMENT_TYPES, required=False)
    date_joined = serializers.DateField(required=False)
    is_active = serializers.BooleanField(required=False)
    section = serializers.CharField(max_length=10, required=False, allow_blank=True)
    subsection = serializers.CharField(max_length=10, required=False, allow_blank=True)

    def update(self, instance, validated_data):
        # Update User fields
        user = instance.user
        if "first_name" in validated_data:
            user.first_name = validated_data.pop("first_name")
        if "last_name" in validated_data:
            user.last_name = validated_data.pop("last_name")
        user.save()

        # Update Employee fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class EmployeeListSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email")
    first_name = serializers.CharField(source="user.first_name")
    last_name = serializers.CharField(source="user.last_name")

    class Meta:
        model = Employee
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "department",
            "employment_type",
            "date_joined",
            "is_active",
            "section",
            "subsection",
        ]