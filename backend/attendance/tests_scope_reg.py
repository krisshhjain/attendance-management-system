from datetime import timedelta
from django.utils import timezone
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import User, ManagerScope
from employees.models import Employee
from attendance.models import RegularizationRequest

class RegularizationScopeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        # Managers
        self.manager_a = User.objects.create_user("manager_a@example.com", "password", is_system_admin=True)
        ManagerScope.objects.create(manager=self.manager_a, scope_type="SECTION", value="C")
        
        self.manager_b = User.objects.create_user("manager_b@example.com", "password", is_system_admin=True)
        ManagerScope.objects.create(manager=self.manager_b, scope_type="SECTION", value="D")
        
        self.manager_c = User.objects.create_user("manager_c@example.com", "password", is_system_admin=True)
        ManagerScope.objects.create(manager=self.manager_c, scope_type="DEPARTMENT", value="Engineering")

        self.superuser = User.objects.create_superuser("super@example.com", "password")
        
        self.inactive_manager = User.objects.create_user("inactive_manager@example.com", "password", is_system_admin=True, is_active=False)
        ManagerScope.objects.create(manager=self.inactive_manager, scope_type="DEPARTMENT", value="Engineering")

        self.empty_manager = User.objects.create_user("empty_manager@example.com", "password", is_system_admin=True)

        # Employees
        self.intern_c = Employee.objects.create(
            user=User.objects.create_user("intern_c@example.com", "password"),
            employment_type="INTERN", section="C", department="Engineering", date_joined="2026-01-01"
        )
        self.intern_d = Employee.objects.create(
            user=User.objects.create_user("intern_d@example.com", "password"),
            employment_type="INTERN", section="D", department="Engineering", date_joined="2026-01-01"
        )
        self.perm_eng = Employee.objects.create(
            user=User.objects.create_user("perm_eng@example.com", "password"),
            employment_type="PERMANENT", department="Engineering", section="C", date_joined="2026-01-01"
        )
        self.perm_hr = Employee.objects.create(
            user=User.objects.create_user("perm_hr@example.com", "password"),
            employment_type="PERMANENT", department="HR", date_joined="2026-01-01"
        )

        date = timezone.localdate() - timedelta(days=1)
        self.req_intern_c = RegularizationRequest.objects.create(employee=self.intern_c, attendance_date=date, request_type="INCORRECT_ATTENDANCE", reason="forgot", status="PENDING")
        self.req_intern_d = RegularizationRequest.objects.create(employee=self.intern_d, attendance_date=date, request_type="INCORRECT_ATTENDANCE", reason="forgot", status="PENDING")
        self.req_perm_eng = RegularizationRequest.objects.create(employee=self.perm_eng, attendance_date=date, request_type="INCORRECT_ATTENDANCE", reason="forgot", status="PENDING")
        self.req_perm_hr = RegularizationRequest.objects.create(employee=self.perm_hr, attendance_date=date, request_type="INCORRECT_ATTENDANCE", reason="forgot", status="PENDING")

    def test_manager_a_intern_c(self):
        self.client.force_authenticate(user=self.manager_a)
        
        # List
        res = self.client.get("/api/attendance/admin/regularization/")
        ids = [r["id"] for r in res.data]
        self.assertIn(self.req_intern_c.id, ids)
        self.assertNotIn(self.req_intern_d.id, ids)
        self.assertNotIn(self.req_perm_eng.id, ids)

        # Detail scoped
        self.assertEqual(self.client.get(f"/api/attendance/admin/regularization/{self.req_intern_c.id}/").status_code, 200)
        # Detail out-of-scope
        self.assertEqual(self.client.get(f"/api/attendance/admin/regularization/{self.req_intern_d.id}/").status_code, 403)
        self.assertEqual(self.client.get(f"/api/attendance/admin/regularization/{self.req_perm_eng.id}/").status_code, 403)

        # Reject out-of-scope (Approval requires times so it's harder to test here, reject just needs reason)
        self.assertEqual(self.client.post(f"/api/attendance/admin/regularization/{self.req_intern_d.id}/reject/", {"rejection_reason": "no"}).status_code, 403)

    def test_manager_c_perm_eng(self):
        self.client.force_authenticate(user=self.manager_c)
        res = self.client.get("/api/attendance/admin/regularization/")
        ids = [r["id"] for r in res.data]
        self.assertIn(self.req_perm_eng.id, ids)
        self.assertNotIn(self.req_intern_c.id, ids)
        self.assertNotIn(self.req_perm_hr.id, ids)

        self.assertEqual(self.client.get(f"/api/attendance/admin/regularization/{self.req_perm_hr.id}/").status_code, 403)

    def test_superuser_unrestricted(self):
        self.client.force_authenticate(user=self.superuser)
        res = self.client.get("/api/attendance/admin/regularization/")
        self.assertEqual(len(res.data), 4)
        self.assertEqual(self.client.get(f"/api/attendance/admin/regularization/{self.req_perm_hr.id}/").status_code, 200)

    def test_empty_inactive_manager(self):
        self.client.force_authenticate(user=self.inactive_manager)
        self.assertEqual(len(self.client.get("/api/attendance/admin/regularization/").data), 0)
        self.assertEqual(self.client.get(f"/api/attendance/admin/regularization/{self.req_perm_eng.id}/").status_code, 403)

        self.client.force_authenticate(user=self.empty_manager)
        self.assertEqual(len(self.client.get("/api/attendance/admin/regularization/").data), 0)
        self.assertEqual(self.client.get(f"/api/attendance/admin/regularization/{self.req_perm_eng.id}/").status_code, 403)
