from rest_framework import serializers
from .models import OfficeLocation


class OfficeLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = OfficeLocation
        fields = [
            "id",
            "name",
            "latitude",
            "longitude",
            "radius_meters",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_latitude(self, value):
        if value < -90.0 or value > 90.0:
            raise serializers.ValidationError("Latitude must be between -90 and 90 degrees.")
        return value

    def validate_longitude(self, value):
        if value < -180.0 or value > 180.0:
            raise serializers.ValidationError("Longitude must be between -180 and 180 degrees.")
        return value

    def validate_name(self, value):
        cleaned_name = value.strip() if isinstance(value, str) else ""
        if not cleaned_name:
            raise serializers.ValidationError("Location name cannot be empty.")
        return cleaned_name
