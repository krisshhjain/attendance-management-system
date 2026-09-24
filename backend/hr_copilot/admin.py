from django.contrib import admin

from .models import CopilotQueryAudit


@admin.register(CopilotQueryAudit)
class CopilotQueryAuditAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "validation_result", "scope_result", "execution_result", "error_code")
    list_filter = ("validation_result", "scope_result", "execution_result", "created_at")
    search_fields = ("user__email", "question", "error_code")
    readonly_fields = tuple(field.name for field in CopilotQueryAudit._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
