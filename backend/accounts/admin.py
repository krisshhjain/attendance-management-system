from django.contrib import admin
from django.contrib import admin
from django.contrib.auth import get_user_model

User = get_user_model()


@admin.register(User)
class CustomUserAdmin(admin.ModelAdmin):
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "is_staff", "is_system_admin")
    fields = (
        "email", "first_name", "last_name", "is_active", "is_staff", "is_superuser",
        "is_system_admin", "hr_copilot_sections", "hr_copilot_subsections",
    )
    search_fields = ("email", "first_name", "last_name")

    def has_add_permission(self, request):
        return False
