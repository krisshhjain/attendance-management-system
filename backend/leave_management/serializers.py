from rest_framework import serializers
from .models import LeaveType, LeavePolicy, LeaveRequest


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = [
            "id",
            "name",
            "code",
            "description",
            "is_active",
            "is_paid",
            "requires_document",
            "allow_half_day",
            "allow_past_dates",
            "allow_future_dates",
            "min_notice_days",
            "created_at",
            "updated_at",
        ]


class LeavePolicySerializer(serializers.ModelSerializer):
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)
    leave_type_code = serializers.CharField(source="leave_type.code", read_only=True)

    class Meta:
        model = LeavePolicy
        fields = [
            "id",
            "employee_type",
            "leave_type",
            "leave_type_name",
            "leave_type_code",
            "annual_entitlement",
            "allow_carry_forward",
            "max_carry_forward",
            "unused_expires",
            "max_consecutive_days",
            "min_notice_days",
            "allow_half_day",
            "requires_document",
            "effective_from",
            "effective_to",
            "is_active",
            "created_at",
            "updated_at",
        ]


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_id = serializers.IntegerField(source="employee.id", read_only=True)
    employee_email = serializers.CharField(source="employee.user.email", read_only=True)
    employee_name = serializers.SerializerMethodField()
    employee_department = serializers.CharField(source="employee.department", read_only=True)
    employment_type = serializers.CharField(source="employee.employment_type", read_only=True)
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)
    leave_type_code = serializers.CharField(source="leave_type.code", read_only=True)
    reviewed_by_email = serializers.CharField(source="reviewed_by.email", read_only=True, default=None)
    cancelled_by_email = serializers.CharField(source="cancelled_by.email", read_only=True, default=None)

    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "employee_id",
            "employee_email",
            "employee_name",
            "employee_department",
            "employment_type",
            "leave_type",
            "leave_type_name",
            "leave_type_code",
            "start_date",
            "end_date",
            "day_type",
            "duration_days",
            "reason",
            "attachment",
            "status",
            "submitted_at",
            "reviewed_at",
            "reviewed_by_email",
            "reviewer_remarks",
            "cancelled_at",
            "cancelled_by_email",
        ]

    def get_employee_name(self, obj):
        first = obj.employee.user.first_name
        last = obj.employee.user.last_name
        if first or last:
            return f"{first} {last}".strip()
        return obj.employee.user.email


class CreateLeaveRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveRequest
        fields = [
            "leave_type",
            "start_date",
            "end_date",
            "day_type",
            "reason",
            "attachment",
        ]
