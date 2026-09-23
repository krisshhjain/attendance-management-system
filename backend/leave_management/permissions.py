from rest_framework.permissions import BasePermission, IsAuthenticated


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_superuser
        )


class IsAdminOrSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or request.user.is_superuser)
        )


class IsSystemAdminOrSuperAdminReadOnly(BasePermission):
    """Allow System Admin reads while reserving configuration changes for superusers."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return user.is_system_admin or user.is_superuser
        return user.is_superuser


class IsEmployee(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, "employee")
            and request.user.employee.is_active
        )
