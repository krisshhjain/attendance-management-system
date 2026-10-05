from django.core.exceptions import PermissionDenied

from .models import ManagerScope


def get_manager_scope(manager):
    """Return authoritative active scope records for a Manager.

    SuperUsers are represented explicitly as unrestricted. All other users,
    including inactive or unscoped Managers, receive no effective scope.
    """
    if getattr(manager, "is_superuser", False):
        return {"unrestricted": True, "sections": set(), "departments": set()}

    if not getattr(manager, "is_authenticated", False):
        return {"unrestricted": False, "sections": set(), "departments": set()}
    if not getattr(manager, "is_system_admin", False) or not getattr(manager, "is_active", False):
        return {"unrestricted": False, "sections": set(), "departments": set()}

    records = ManagerScope.objects.filter(manager=manager, is_active=True)
    return {
        "unrestricted": False,
        "sections": {r.value for r in records if r.scope_type == ManagerScope.SECTION},
        "departments": {r.value for r in records if r.scope_type == ManagerScope.DEPARTMENT},
    }


def employee_in_manager_scope(manager, employee):
    scope = get_manager_scope(manager)
    if scope["unrestricted"]:
        return True
    if not scope["sections"] and not scope["departments"]:
        return False
    if employee.employment_type == "INTERN":
        return employee.section in scope["sections"]
    if employee.employment_type == "PERMANENT":
        return employee.department in scope["departments"]
    return False


def filter_employees_by_manager_scope(manager, queryset):
    scope = get_manager_scope(manager)
    if scope["unrestricted"]:
        return queryset
    if not scope["sections"] and not scope["departments"]:
        return queryset.none()
    from django.db.models import Q
    return queryset.filter(
        Q(employment_type="INTERN", section__in=scope["sections"])
        | Q(employment_type="PERMANENT", department__in=scope["departments"])
    )


def assert_employee_in_manager_scope(manager, employee):
    if not employee_in_manager_scope(manager, employee):
        raise PermissionDenied("You do not have access to that employee.")
