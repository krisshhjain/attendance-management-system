from rest_framework import serializers

from .models import Holiday


class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = ["id", "date", "name", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_name(self, value):
        cleaned = value.strip() if isinstance(value, str) else ""
        if not cleaned:
            raise serializers.ValidationError("Holiday name cannot be empty.")
        return cleaned

    def validate_date(self, value):
        matches = Holiday.objects.filter(date=value)
        if self.instance:
            matches = matches.exclude(pk=self.instance.pk)
        if matches.exists():
            raise serializers.ValidationError("A holiday already exists for this date.")
        return value
