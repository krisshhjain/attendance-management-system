from datetime import timedelta
from django.utils import timezone
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import User, ManagerScope
from employees.models import Employee
from leave_management.models import LeaveType, LeavePolicy, LeaveRequest

class LeaveScopeTests(TestCase):
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

        # Leave setup
        self.leave_type = LeaveType.objects.create(name="Annual", code="AL")
        LeavePolicy.objects.create(employee_type="INTERN", leave_type=self.leave_type, annual_entitlement=10, effective_from="2020-01-01")
        LeavePolicy.objects.create(employee_type="PERMANENT", leave_type=self.leave_type, annual_entitlement=20, effective_from="2020-01-01")

        # Requests
        date = timezone.localdate() + timedelta(days=5)
        self.req_intern_c = LeaveRequest.objects.create(employee=self.intern_c, leave_type=self.leave_type, start_date=date, end_date=date, day_type="FULL", status="PENDING", duration_days=1)
        self.req_intern_d = LeaveRequest.objects.create(employee=self.intern_d, leave_type=self.leave_type, start_date=date, end_date=date, day_type="FULL", status="PENDING", duration_days=1)
        self.req_perm_eng = LeaveRequest.objects.create(employee=self.perm_eng, leave_type=self.leave_type, start_date=date, end_date=date, day_type="FULL", status="PENDING", duration_days=1)
        self.req_perm_hr = LeaveRequest.objects.create(employee=self.perm_hr, leave_type=self.leave_type, start_date=date, end_date=date, day_type="FULL", status="PENDING", duration_days=1)

    def test_manager_a_intern_c(self):
        self.client.force_authenticate(user=self.manager_a)
        
        # List
        res = self.client.get("/api/leave/admin/requests/")
        ids = [r["id"] for r in res.data]
        self.assertIn(self.req_intern_c.id, ids)
        self.assertNotIn(self.req_intern_d.id, ids)
        self.assertNotIn(self.req_perm_eng.id, ids)

        # Detail scoped
        self.assertEqual(self.client.get(f"/api/leave/admin/requests/{self.req_intern_c.id}/").status_code, 200)
        # Detail out-of-scope
        self.assertEqual(self.client.get(f"/api/leave/admin/requests/{self.req_intern_d.id}/").status_code, 403)
        self.assertEqual(self.client.get(f"/api/leave/admin/requests/{self.req_perm_eng.id}/").status_code, 403)

        # Approve scoped
        self.assertEqual(self.client.post(f"/api/leave/admin/requests/{self.req_intern_c.id}/approve/", {"remarks": "ok"}).status_code, 200)
        
        # Deny out-of-scope
        self.assertEqual(self.client.post(f"/api/leave/admin/requests/{self.req_intern_d.id}/deny/", {"remarks": "no"}).status_code, 403)

        # Balances
        res = self.client.get("/api/leave/admin/balances/")
        emp_ids = [r["employee_id"] for r in res.data]
        self.assertIn(self.intern_c.id, emp_ids)
        self.assertNotIn(self.perm_eng.id, emp_ids)

        self.assertEqual(self.client.get(f"/api/leave/admin/balances/?employee_id={self.intern_c.id}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/leave/admin/balances/?employee_id={self.perm_eng.id}").status_code, 403)

    def test_manager_c_perm_eng(self):
        self.client.force_authenticate(user=self.manager_c)
        res = self.client.get("/api/leave/admin/requests/")
        ids = [r["id"] for r in res.data]
        self.assertIn(self.req_perm_eng.id, ids)
        # Manager C scope is DEPARTMENT Engineering. Wait, intern_c and intern_d have department Engineering!
        # Intern uses Section scope. If an intern is in Engineering, does Manager C see them?
        # Let's check employee_in_manager_scope.
        # "PERMANENT -> DEPARTMENT, INTERN -> SECTION". So manager C's DEPARTMENT scope should NOT match INTERN!
        # Wait, the prompt says "Intern uses Section, Permanent uses Department".
        self.assertNotIn(self.req_intern_c.id, ids)
        self.assertNotIn(self.req_perm_hr.id, ids)

        self.assertEqual(self.client.get(f"/api/leave/admin/requests/{self.req_perm_hr.id}/").status_code, 403)

    def test_superuser_unrestricted(self):
        self.client.force_authenticate(user=self.superuser)
        res = self.client.get("/api/leave/admin/requests/")
        self.assertEqual(len(res.data), 4)
        self.assertEqual(self.client.get(f"/api/leave/admin/requests/{self.req_perm_hr.id}/").status_code, 200)

    def test_empty_inactive_manager(self):
        self.client.force_authenticate(user=self.inactive_manager)
        self.assertEqual(len(self.client.get("/api/leave/admin/requests/").data), 0)
        self.assertEqual(self.client.get(f"/api/leave/admin/requests/{self.req_perm_eng.id}/").status_code, 403)

        self.client.force_authenticate(user=self.empty_manager)
        self.assertEqual(len(self.client.get("/api/leave/admin/requests/").data), 0)
        self.assertEqual(self.client.get(f"/api/leave/admin/requests/{self.req_perm_eng.id}/").status_code, 403)
