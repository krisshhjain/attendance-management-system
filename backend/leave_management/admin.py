from django.contrib import admin
from .models import LeaveType, LeavePolicy, LeaveRequest


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "is_active", "is_paid", "allow_half_day")
    search_fields = ("name", "code")
    list_filter = ("is_active", "is_paid")


@admin.register(LeavePolicy)
class LeavePolicyAdmin(admin.ModelAdmin):
    list_display = ("employee_type", "leave_type", "annual_entitlement", "effective_from", "is_active")
    search_fields = ("employee_type", "leave_type__name")
    list_filter = ("employee_type", "is_active")


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("employee", "leave_type", "start_date", "end_date", "duration_days", "status", "submitted_at")
    search_fields = ("employee__user__email", "leave_type__name", "reason")
    list_filter = ("status", "leave_type", "day_type")
