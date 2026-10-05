from datetime import time as datetime_time
from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APITestCase
from accounts.models import User, ManagerScope
from employees.models import Employee
from attendance.models import Shift


class ShiftScopeTests(APITestCase):
    def setUp(self):
        # Managers
        self.manager_a = User.objects.create_user("manager_a@example.com", "password", is_system_admin=True)
        ManagerScope.objects.create(manager=self.manager_a, scope_type="SECTION", value="C")
        
        self.manager_c = User.objects.create_user("manager_c@example.com", "password", is_system_admin=True)
        ManagerScope.objects.create(manager=self.manager_c, scope_type="DEPARTMENT", value="Engineering")
        
        self.superuser = User.objects.create_superuser("super@example.com", "password")

        # Employees
        self.intern_c = Employee.objects.create(
            user=User.objects.create_user("intern_c@example.com", "password"),
            employment_type="INTERN", department="Engineering", section="C", date_joined="2026-01-01", is_active=True
        )
        self.intern_d = Employee.objects.create(
            user=User.objects.create_user("intern_d@example.com", "password"),
            employment_type="INTERN", department="Engineering", section="D", date_joined="2026-01-01", is_active=True
        )
        self.perm_eng = Employee.objects.create(
            user=User.objects.create_user("perm_eng@example.com", "password"),
            employment_type="PERMANENT", department="Engineering", section="C", date_joined="2026-01-01", is_active=True
        )
        self.perm_hr = Employee.objects.create(
            user=User.objects.create_user("perm_hr@example.com", "password"),
            employment_type="PERMANENT", department="HR", section="C", date_joined="2026-01-01", is_active=True
        )

        # Shifts
        self.shift_1 = Shift.objects.create(name="Morning", code="M1", start_time=datetime_time(9, 0), end_time=datetime_time(17, 0), employment_type="PERMANENT", is_active=True)
        self.shift_2 = Shift.objects.create(name="Evening", code="E1", start_time=datetime_time(17, 0), end_time=datetime_time(1, 0), employment_type="INTERN", is_active=True)

    def test_manager_a_intern_c(self):
        self.client.force_authenticate(user=self.manager_a)
        
        # Assign shift within scope
        res = self.client.post("/api/attendance/admin/shift/assign/", {
            "employee_email": self.intern_c.user.email,
            "shift_id": self.shift_2.id
        }, format='json')
        self.assertEqual(res.status_code, 200)

        # Assign shift outside scope (Intern in section D)
        res = self.client.post("/api/attendance/admin/shift/assign/", {
            "employee_email": self.intern_d.user.email,
            "shift_id": self.shift_2.id
        }, format='json')
        self.assertEqual(res.status_code, 403)

        # Bulk assign
        res = self.client.post("/api/attendance/admin/shift/bulk-assign/", {
            "shift_id": self.shift_2.id,
            "employee_emails": [self.intern_c.user.email, self.intern_d.user.email]
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.intern_c.refresh_from_db()
        self.intern_d.refresh_from_db()
        self.assertEqual(self.intern_c.shift_id, self.shift_2.id)
        self.assertNotEqual(self.intern_d.shift_id, self.shift_2.id)

    def test_manager_c_perm_eng(self):
        self.client.force_authenticate(user=self.manager_c)
        
        # Assign shift within scope (PERMANENT Engineering)
        res = self.client.post("/api/attendance/admin/shift/assign/", {
            "employee_email": self.perm_eng.user.email,
            "shift_id": self.shift_1.id
        }, format='json')
        self.assertEqual(res.status_code, 200)

        # Assign shift outside scope (PERMANENT HR)
        res = self.client.post("/api/attendance/admin/shift/assign/", {
            "employee_email": self.perm_hr.user.email,
            "shift_id": self.shift_1.id
        }, format='json')
        self.assertEqual(res.status_code, 403)

    def test_superuser_unrestricted(self):
        self.client.force_authenticate(user=self.superuser)
        
        res = self.client.post("/api/attendance/admin/shift/assign/", {
            "employee_email": self.perm_hr.user.email,
            "shift_id": self.shift_1.id
        }, format='json')
        self.assertEqual(res.status_code, 200)

        res = self.client.post("/api/attendance/admin/shift/bulk-assign/", {
            "shift_id": self.shift_2.id,
            "employee_emails": [self.intern_c.user.email, self.intern_d.user.email]
        }, format='json')
        self.assertEqual(res.status_code, 200)
        self.intern_c.refresh_from_db()
        self.intern_d.refresh_from_db()
        self.assertEqual(self.intern_c.shift_id, self.shift_2.id)
        self.assertEqual(self.intern_d.shift_id, self.shift_2.id)
