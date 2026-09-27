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
    """
    Allow Manager (is_system_admin) reads while reserving 
    configuration changes for SuperUsers.
    """

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return user.is_system_admin or user.is_superuser
        return user.is_superuser


class IsManager(BasePermission):
    """
    Allow only Manager users (is_system_admin=True).
    SuperUsers are NOT allowed - they have separate routes.
    """
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_system_admin
            and not request.user.is_superuser
        )


class IsManagerOrSuperUser(BasePermission):
    """
    Allow Manager (is_system_admin) or SuperUser.
    Used for operations both roles can perform.
    """
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_system_admin or request.user.is_superuser)
        )


class IsManagerOrAdmin(BasePermission):
    """
    Allow Manager (is_system_admin), Admin (is_staff), or SuperUser.
    Used for attendance/leave management operations.
    """
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_system_admin or request.user.is_staff or request.user.is_superuser)
        )


class IsEmployee(BasePermission):
    def has_permission(self, request, view):
        allowed_employee = bool(
            request.user
            and request.user.is_authenticated
            and hasattr(request.user, "employee")
            and request.user.employee.is_active
        )
        if not allowed_employee:
            return False
        access_key = getattr(view, "app_access_key", "leave")
        return request.user.employee.app_access.get(access_key, True)


class IsAdminOrAppAdmin(BasePermission):
    """Allow Admin (is_staff) or Super Admin (is_superuser) for shift management."""
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (request.user.is_staff or request.user.is_superuser)
        )


class IsEmployeeWithShift(BasePermission):
    """Employee must have an assigned shift for attendance operations."""
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and hasattr(request.user, "employee")):
            return False
        employee = request.user.employee
        return employee.is_active and employee.shift is not None
