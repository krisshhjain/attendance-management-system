"""Deterministic HR data tools used after intent and scope validation."""

from .employee_resolver import employee_resolver
from .pipeline import CopilotError, build_sql, execute_query, serialize_result, validate_sql
from employees.models import Employee
from .attendance_intelligence import attendance_intelligence
from .leave_regularization_intelligence import leave_regularization_intelligence
from .workforce_intelligence import workforce_intelligence


class HRTools:
    def execute_attendance_intelligence(self, *, metric, scope, user, filters, employee_id=None):
        return attendance_intelligence.execute(
            metric=metric, scope=scope, user=user, filters=filters, employee_id=employee_id,
        )

    def execute_leave_regularization_intelligence(self, *, metric, scope, user, filters, employee_id=None):
        return leave_regularization_intelligence.execute(
            metric=metric, scope=scope, user=user, filters=filters, employee_id=employee_id,
        )

    def execute_workforce_intelligence(self, *, metric, scope, user, filters, employee_id=None):
        return workforce_intelligence.execute(
            metric=metric, scope=scope, user=user, filters=filters, employee_id=employee_id,
        )
    def get_employee_profile(self, *, employee_id, scope):
        resolution = employee_resolver.resolve_employee(employee_id=employee_id)
        if resolution.status != "resolved":
            raise CopilotError("employee_not_found", "No employee matched that identity.")
        employee = Employee.objects.select_related("user").filter(pk=resolution.employee_id).first()
        if employee is None:
            raise CopilotError("employee_not_found", "No employee matched that identity.")
        if not scope["unrestricted"] and (
            employee.section not in scope["sections"]
            or (scope["subsections"] and employee.subsection not in scope["subsections"])
        ):
            raise CopilotError("scope_denied", "You do not have access to that employee.", 403)
        return [{
            "id": employee.id,
            "name": " ".join(part for part in [employee.user.first_name, employee.user.last_name] if part).strip(),
            "email": employee.user.email,
            "department": employee.department,
            "employment_type": employee.employment_type,
            "section": employee.section,
            "subsection": employee.subsection,
            "is_active": employee.is_active,
            "date_joined": employee.date_joined.isoformat(),
        }]

    def execute_plan(self, plan, *, execute_query_fn=execute_query, validate_sql_fn=validate_sql):
        sql, params = build_sql(plan)
        validate_sql_fn(sql, plan)
        columns, rows = execute_query_fn(sql, params)
        return sql, serialize_result(columns, rows), columns


hr_tools = HRTools()
