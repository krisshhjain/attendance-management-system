"""Database-backed employee identity resolution for the HR Copilot."""

from dataclasses import dataclass

from django.db.models import Q

from employees.models import Employee


@dataclass(frozen=True)
class EmployeeResolution:
    status: str
    employee_id: int | None = None

    def as_dict(self):
        return {"status": self.status, "employee_id": self.employee_id}


class EmployeeResolver:
    """Resolve only real employee records; never trust an LLM-provided identity."""

    def resolve_employee(self, *, user=None, name=None, email=None, employee_id=None):
        supplied = [value for value in (name, email, employee_id) if value not in (None, "")]
        if not supplied:
            return EmployeeResolution("missing")
        if len(supplied) > 1:
            return EmployeeResolution("ambiguous")

        if employee_id is not None:
            try:
                employee_id = int(employee_id)
            except (TypeError, ValueError):
                return EmployeeResolution("not_found")
            matches = Employee.objects.filter(pk=employee_id)
        elif email:
            matches = Employee.objects.filter(user__email__iexact=email.strip())
        else:
            parts = name.split()
            if len(parts) == 1:
                matches = Employee.objects.filter(
                    Q(user__first_name__iexact=parts[0]) | Q(user__last_name__iexact=parts[0])
                )
            else:
                matches = Employee.objects.filter(
                    user__first_name__iexact=parts[0],
                    user__last_name__iexact=" ".join(parts[1:]),
                )

        if user:
            from accounts.scope_service import filter_employees_by_manager_scope
            matches = filter_employees_by_manager_scope(user, matches)
        matching_ids = list(matches.values_list("id", flat=True)[:2])
        if not matching_ids:
            return EmployeeResolution("not_found")
        if len(matching_ids) > 1:
            return EmployeeResolution("ambiguous")
        return EmployeeResolution("resolved", matching_ids[0])


employee_resolver = EmployeeResolver()
