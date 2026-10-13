from datetime import date

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import ManagerScope, User
from employees.models import Employee


class EmployeeViewScopeCoverageTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            email="manager-view@example.test", is_system_admin=True
        )
        ManagerScope.objects.create(
            manager=self.manager, scope_type="SECTION", value="C"
        )
        ManagerScope.objects.create(
            manager=self.manager,
            scope_type="DEPARTMENT",
            value="Engineering",
        )
        self.employee_user = User.objects.create_user(
            email="employee-view@example.test",
            first_name="Asha",
            last_name="Rao",
        )
        self.employee = Employee.objects.create(
            user=self.employee_user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined=date(2025, 1, 1),
            section="C",
            subsection="C1",
        )
        self.out_of_scope_user = User.objects.create_user(
            email="outside-view@example.test"
        )
        self.out_of_scope = Employee.objects.create(
            user=self.out_of_scope_user,
            department="Marketing",
            employment_type="PERMANENT",
            date_joined=date(2025, 1, 1),
            section="D",
            subsection="D1",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.manager)

    def test_manager_cannot_patch_or_delete_employee_outside_scope(self):
        url = f"/api/admin/employees/{self.out_of_scope.id}/"

        patched = self.client.patch(url, {"first_name": "Changed"})
        deleted = self.client.delete(url)

        self.assertEqual(patched.status_code, 403)
        self.assertEqual(deleted.status_code, 403)
        self.out_of_scope_user.refresh_from_db()
        self.out_of_scope.refresh_from_db()
        self.assertEqual(self.out_of_scope_user.first_name, "")
        self.assertTrue(Employee.objects.filter(pk=self.out_of_scope.pk).exists())

    def test_manager_patch_updates_in_scope_employee(self):
        response = self.client.patch(
            f"/api/admin/employees/{self.employee.id}/",
            {"department": "People Operations"},
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.department, "People Operations")
        self.assertEqual(response.data["department"], "People Operations")

    def test_manager_receives_not_found_for_missing_employee(self):
        response = self.client.get("/api/admin/employees/999999/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["error"], "Employee not found.")
