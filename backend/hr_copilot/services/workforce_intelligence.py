"""Read-only, scope-aware workforce and administration intelligence."""

from collections import Counter

from attendance.models import OfficeLocation, Shift
from employees.models import Employee, FaceProfile
from .pipeline import CopilotError


METRICS = {
    "employee_search", "employee_details", "org_counts", "manager_info",
    "shift_assignments", "shift_configuration", "face_enrollment",
    "office_locations", "employee_status", "access_status",
}


def _name(employee):
    return employee.user.get_full_name().strip() or employee.user.email


class WorkforceIntelligence:
    def _employees(self, user, scope, employee_id=None, filters=None):
        filters = filters or {}
        qs = Employee.objects.select_related("user", "shift").prefetch_related("face_profile")
        if user:
            from accounts.scope_service import filter_employees_by_manager_scope
            qs = filter_employees_by_manager_scope(user, qs)
        if employee_id:
            employee = qs.filter(pk=employee_id).first()
            if not employee:
                raise CopilotError("scope_denied", "You do not have access to that employee.", 403)
            return qs.filter(pk=employee_id)
        for key in ("department", "section", "subsection", "employment_type"):
            if filters.get(key):
                qs = qs.filter(**{key: filters[key]})
        if filters.get("shift_name"):
            qs = qs.filter(shift__name__iexact=filters["shift_name"])
        if filters.get("shift_id"):
            qs = qs.filter(shift_id=filters["shift_id"])
        if "is_active" in filters:
            qs = qs.filter(is_active=filters["is_active"])
        return qs.order_by("user__last_name", "user__first_name", "id")

    @staticmethod
    def _employee_row(employee, include_access=True):
        profile = getattr(employee, "face_profile", None)
        shift = employee.get_effective_shift()
        row = {
            "employee_id": employee.id, "name": _name(employee), "email": employee.user.email,
            "department": employee.department, "employment_type": employee.employment_type,
            "section": employee.section, "subsection": employee.subsection,
            "is_active": employee.is_active, "user_active": employee.user.is_active,
            "must_change_password": employee.must_change_password,
            "face_enrolled": bool(profile and profile.status == "ACTIVE"),
            "face_status": profile.status if profile else "NOT_ENROLLED",
            "shift_id": shift.id if shift else None, "shift_code": shift.code if shift else None,
            "shift_name": shift.name if shift else None,
        }
        if include_access:
            row["app_access"] = dict(employee.app_access or {})
        return row

    def execute(self, *, metric, scope, user, filters, employee_id=None):
        if metric not in METRICS:
            raise CopilotError("invalid_intelligence_metric", "That workforce query is not supported.")
        employees = self._employees(user, scope, employee_id, filters)
        if metric in {"employee_search", "employee_details", "employee_status", "access_status", "face_enrollment"}:
            rows = [self._employee_row(employee, include_access=metric in {"employee_details", "access_status"}) for employee in employees]
            if metric == "employee_status":
                rows = [row for row in rows if row["is_active"] == filters.get("is_active", row["is_active"])]
            if metric == "face_enrollment":
                enrolled = filters.get("face_enrolled")
                if enrolled is not None:
                    rows = [row for row in rows if row["face_enrolled"] == enrolled]
            if metric == "access_status" and filters.get("access_key"):
                key = filters["access_key"]
                rows = [{**row, "access_key": key, "access_enabled": bool(row["app_access"].get(key, False))} for row in rows]
            return self._result(metric, rows, "Employee results are limited to the authenticated Copilot scope and use effective shift and face-profile status.")
        if metric == "org_counts":
            rows = []
            for field in ("department", "section", "subsection"):
                counts = Counter(getattr(employee, field) or "UNASSIGNED" for employee in employees)
                rows.extend({"group_by": field, "value": key, "employee_count": count} for key, count in sorted(counts.items()))
            return self._result(metric, rows, "Counts include employees in the authenticated scope and respect the requested employee filters.")
        if metric == "manager_info":
            from django.contrib.auth import get_user_model
            User = get_user_model()
            managers = User.objects.filter(is_system_admin=True, is_superuser=False, is_active=True)
            managers = [manager for manager in managers if scope["unrestricted"] or set(manager.hr_copilot_sections or []).intersection(scope["sections"])]
            rows = [{
                "manager_id": manager.id, "name": manager.get_full_name().strip() or manager.email,
                "email": manager.email, "sections": manager.hr_copilot_sections,
                "subsections": manager.hr_copilot_subsections,
                "team_employee_count": self._employees(
                    scope if scope["unrestricted"] else {
                        **scope,
                        "sections": sorted(set(manager.hr_copilot_sections or []).intersection(scope["sections"])),
                        "subsections": sorted(set(manager.hr_copilot_subsections or []).intersection(scope["subsections"] if scope["subsections"] else set(manager.hr_copilot_subsections or []))) or None,
                    }
                ).count(),
            } for manager in sorted(managers, key=lambda manager: (manager.last_name, manager.first_name, manager.id))]
            return self._result(metric, rows, "Manager information is limited to active Copilot managers whose configured scope overlaps the requester's scope.")
        if metric == "shift_assignments" and employee_id:
            employee = employees.first()
            row = self._employee_row(employee, include_access=False) if employee else None
            if row is None:
                return self._result(metric, [], "The requested employee is outside the authenticated Copilot scope.")
            # This branch is deliberately employee-centric. It must never
            # fall back to the list of configured shifts.
            shift = employee.shift
            row.update({
                "assigned_shift_id": shift.id if shift else None,
                "assigned_shift_code": shift.code if shift else None,
                "assigned_shift_name": shift.name if shift else None,
            })
            return self._result(metric, [row], "The result uses the employee's explicit Employee-to-Shift assignment.")
        if metric == "shift_assignments":
            rows = [self._employee_row(employee, include_access=False) for employee in employees]
            return self._result(metric, rows, "Employee shift results use explicit Employee-to-Shift assignments and the authenticated scope.")
        if metric == "shift_configuration":
            shifts = Shift.objects.filter(is_active=True).order_by("employment_type", "code")
            rows = []
            for shift in shifts:
                assigned = employees.filter(shift=shift).count()
                rows.append({"shift_id": shift.id, "code": shift.code, "name": shift.name,
                             "employment_type": shift.employment_type or None,
                             "start_time": shift.start_time.strftime("%H:%M"), "end_time": shift.end_time.strftime("%H:%M"),
                             "is_active": shift.is_active, "assigned_employee_count": assigned})
            return self._result(metric, rows, "Shift assignments use explicit employee assignments; effective auto-selection is included in employee results.")
        if metric == "office_locations":
            rows = [{"id": location.id, "name": location.name, "latitude": location.latitude,
                     "longitude": location.longitude, "radius_meters": location.radius_meters,
                     "is_active": location.is_active} for location in OfficeLocation.objects.order_by("name")]
            return self._result(metric, rows, "Office locations are read-only configuration records visible to the authorized Copilot user.")

    @staticmethod
    def _result(metric, rows, assumption):
        return {"metric": metric, "date_range": None, "assumptions": [assumption], "rows": rows}


workforce_intelligence = WorkforceIntelligence()
