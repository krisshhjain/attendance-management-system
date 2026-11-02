from django.test import TestCase
from employees.models import Employee
from employees.serializers import (
    EmployeeCreateSerializer,
    EmployeeUpdateSerializer,
)
from employees.views import _normalize_manager_scopes

from .models import ManagerScope, User
from .scope_service import (
    employee_in_manager_scope,
    filter_employees_by_manager_scope,
)


class ManagerScopeFoundationTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            "manager@example.com", "password", is_system_admin=True
        )
        self.superuser = User.objects.create_superuser(
            "root@example.com", "password"
        )

    def employee(self, email, kind, section="", department=""):
        return Employee.objects.create(
            user=User.objects.create_user(email, "password"),
            employment_type=kind,
            section=section,
            department=department,
            date_joined="2026-01-01",
        )

    def test_intern_section_scope_and_multiple_scopes(self):
        ManagerScope.objects.create(
            manager=self.manager, scope_type="SECTION", value="C"
        )
        ManagerScope.objects.create(
            manager=self.manager, scope_type="SECTION", value="D"
        )
        self.assertTrue(
            employee_in_manager_scope(
                self.manager,
                self.employee("c@example.com", "INTERN", section="C"),
            )
        )
        self.assertTrue(
            employee_in_manager_scope(
                self.manager,
                self.employee("d@example.com", "INTERN", section="D"),
            )
        )
        self.assertFalse(
            employee_in_manager_scope(
                self.manager,
                self.employee("e@example.com", "INTERN", section="E"),
            )
        )

    def test_permanent_department_scope_does_not_cross_match(self):
        ManagerScope.objects.create(
            manager=self.manager, scope_type="DEPARTMENT", value="Engineering"
        )
        self.assertTrue(
            employee_in_manager_scope(
                self.manager,
                self.employee(
                    "eng@example.com", "PERMANENT", department="Engineering"
                ),
            )
        )
        self.assertFalse(
            employee_in_manager_scope(
                self.manager,
                self.employee(
                    "fin@example.com", "PERMANENT", department="Finance"
                ),
            )
        )
        self.assertFalse(
            employee_in_manager_scope(
                self.manager,
                self.employee(
                    "intern@example.com",
                    "INTERN",
                    section="Eng",
                    department="Engineering",
                ),
            )
        )

    def test_empty_and_inactive_manager_are_denied(self):
        employee = self.employee("c@example.com", "INTERN", section="C")
        self.assertFalse(employee_in_manager_scope(self.manager, employee))
        self.manager.is_active = False
        self.manager.save(update_fields=["is_active"])
        ManagerScope.objects.create(
            manager=self.manager, scope_type="SECTION", value="C"
        )
        self.assertFalse(employee_in_manager_scope(self.manager, employee))

    def test_contract_department_scope_and_queryset_consistency(self):
        ManagerScope.objects.create(
            manager=self.manager,
            scope_type="DEPARTMENT",
            value="Engineering",
        )
        allowed = self.employee(
            "contract-eng@example.com", "CONTRACT", department="Engineering"
        )
        denied = self.employee(
            "contract-fin@example.com", "CONTRACT", department="Finance"
        )
        intern = self.employee(
            "intern-eng@example.com",
            "INTERN",
            section="C",
            department="Engineering",
        )

        self.assertTrue(employee_in_manager_scope(self.manager, allowed))
        self.assertFalse(employee_in_manager_scope(self.manager, denied))
        self.assertFalse(employee_in_manager_scope(self.manager, intern))

        queryset = Employee.objects.filter(
            pk__in=[allowed.pk, denied.pk, intern.pk]
        )
        visible_ids = set(
            filter_employees_by_manager_scope(
                self.manager, queryset
            ).values_list("pk", flat=True)
        )
        expected_ids = {
            employee.pk
            for employee in [allowed, denied, intern]
            if employee_in_manager_scope(self.manager, employee)
        }
        self.assertEqual(visible_ids, {allowed.pk})
        self.assertEqual(visible_ids, expected_ids)

    def test_contract_not_authorized_by_section_only(self):
        ManagerScope.objects.create(
            manager=self.manager, scope_type="SECTION", value="C"
        )
        contract = self.employee(
            "contract-section@example.com",
            "CONTRACT",
            section="C",
            department="Engineering",
        )
        self.assertFalse(employee_in_manager_scope(self.manager, contract))
        self.assertFalse(
            filter_employees_by_manager_scope(
                self.manager,
                Employee.objects.filter(pk=contract.pk),
            ).exists()
        )

    def test_inactive_manager_cannot_access_contract_employees(self):
        ManagerScope.objects.create(
            manager=self.manager,
            scope_type="DEPARTMENT",
            value="Engineering",
        )
        contract = self.employee(
            "inactive-contract@example.com",
            "CONTRACT",
            department="Engineering",
        )
        self.manager.is_active = False
        self.manager.save(update_fields=["is_active"])
        self.assertFalse(employee_in_manager_scope(self.manager, contract))
        self.assertFalse(
            filter_employees_by_manager_scope(
                self.manager, Employee.objects.filter(pk=contract.pk)
            ).exists()
        )

    def test_unscoped_manager_cannot_access_contract_employees(self):
        contract = self.employee(
            "unscoped-contract@example.com",
            "CONTRACT",
            department="Engineering",
        )
        self.assertFalse(employee_in_manager_scope(self.manager, contract))
        self.assertFalse(
            filter_employees_by_manager_scope(
                self.manager, Employee.objects.filter(pk=contract.pk)
            ).exists()
        )

    def test_superuser_can_access_contract_employees_without_scope(self):
        contract = self.employee(
            "root-contract@example.com",
            "CONTRACT",
            department="Engineering",
        )
        self.assertTrue(employee_in_manager_scope(self.superuser, contract))
        visible_ids = filter_employees_by_manager_scope(
            self.superuser, Employee.objects.all()
        ).values_list("pk", flat=True)
        self.assertIn(contract.pk, visible_ids)

    def test_department_scope_does_not_authorize_intern_by_department(self):
        ManagerScope.objects.create(
            manager=self.manager,
            scope_type="DEPARTMENT",
            value="Engineering",
        )
        intern = self.employee(
            "department-intern@example.com",
            "INTERN",
            section="C",
            department="Engineering",
        )
        self.assertFalse(employee_in_manager_scope(self.manager, intern))
        self.assertFalse(
            filter_employees_by_manager_scope(
                self.manager, Employee.objects.filter(pk=intern.pk)
            ).exists()
        )

    def test_unknown_employment_type_is_denied_by_both_scope_paths(self):
        ManagerScope.objects.create(
            manager=self.manager,
            scope_type="DEPARTMENT",
            value="Engineering",
        )
        unknown = self.employee(
            "unknown-type@example.com", "UNKNOWN", department="Engineering"
        )
        self.assertFalse(employee_in_manager_scope(self.manager, unknown))
        self.assertFalse(
            filter_employees_by_manager_scope(
                self.manager, Employee.objects.filter(pk=unknown.pk)
            ).exists()
        )

    def test_superuser_is_unrestricted(self):
        employee = self.employee("x@example.com", "INTERN", section="X")
        self.assertTrue(employee_in_manager_scope(self.superuser, employee))
        self.assertEqual(
            filter_employees_by_manager_scope(
                self.superuser, Employee.objects.all()
            ).count(),
            1,
        )

    def test_employee_registration_rules(self):
        base = {
            "email": "intern@example.com",
            "password": "password123",
            "department": "Engineering",
            "employment_type": "INTERN",
            "date_joined": "2026-01-01",
        }
        serializer = EmployeeCreateSerializer(data=base)
        self.assertFalse(serializer.is_valid())
        self.assertIn("section", serializer.errors)

        permanent = dict(
            base, email="permanent@example.com", employment_type="PERMANENT"
        )
        self.assertTrue(EmployeeCreateSerializer(data=permanent).is_valid())

    def test_employment_type_change_revalidates_requirements(self):
        employee = self.employee(
            "permanent@example.com", "PERMANENT", department="Engineering"
        )
        serializer = EmployeeUpdateSerializer(
            employee, data={"employment_type": "INTERN"}, partial=True
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("section", serializer.errors)

    def test_invalid_and_duplicate_scope_payloads(self):
        with self.assertRaises(ValueError):
            _normalize_manager_scopes([{"scope_type": "TEAM", "value": "A"}])
        normalized = _normalize_manager_scopes(
            [
                {"scope_type": "SECTION", "value": "C"},
                {"scope_type": "SECTION", "value": "C"},
            ]
        )
        self.assertEqual(normalized, {("SECTION", "C")})

    def test_legacy_json_does_not_authorize_without_authoritative_scope(self):
        self.manager.hr_copilot_sections = ["C"]
        self.manager.hr_copilot_subsections = ["C1"]
        self.manager.save(
            update_fields=["hr_copilot_sections", "hr_copilot_subsections"]
        )
        employee = self.employee("legacy@example.com", "INTERN", section="C")
        self.assertFalse(employee_in_manager_scope(self.manager, employee))
