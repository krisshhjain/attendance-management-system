from django.test import TestCase
from rest_framework.test import APIClient
from system_logs.models import SystemLog

from .models import User


class SystemAdminLoginViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(
            email="quality-manager@example.test",
            password="test-password",
            is_system_admin=True,
        )
        self.employee = User.objects.create_user(
            email="quality-employee@example.test",
            password="test-password",
        )
        self.superuser = User.objects.create_superuser(
            email="quality-root@example.test",
            password="test-password",
            is_system_admin=True,
        )

    def login(self, user, password="test-password"):
        return self.client.post(
            "/api/auth/systemadmin-login/",
            {"email": user.email, "password": password},
            format="json",
        )

    def test_manager_login_succeeds_and_records_success_event(self):
        response = self.login(self.manager)

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertTrue(
            SystemLog.objects.filter(
                event_type="LOGIN_SUCCESS", actor=self.manager
            ).exists()
        )

    def test_non_manager_and_superuser_are_rejected_and_audited(self):
        employee_response = self.login(self.employee)
        root_response = self.login(self.superuser)

        self.assertEqual(employee_response.status_code, 403)
        self.assertIn("Manager privileges", employee_response.data["detail"])
        self.assertEqual(root_response.status_code, 403)
        self.assertIn("admin login", root_response.data["detail"])
        failed = SystemLog.objects.filter(event_type="LOGIN_FAILED")
        self.assertEqual(failed.count(), 2)

    def test_bad_password_is_audited_without_issuing_a_token(self):
        response = self.login(self.manager, password="wrong-password")

        self.assertEqual(response.status_code, 401)
        self.assertNotIn("access", response.data)
        self.assertTrue(
            SystemLog.objects.filter(
                event_type="LOGIN_FAILED",
                message__contains=self.manager.email,
            ).exists()
        )

    def test_change_password_rejects_an_incorrect_current_password(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            "/api/auth/change-password/",
            {
                "current_password": "wrong-current-password",
                "new_password": "Secure-New-123!abc",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("incorrect", str(response.data["current_password"]))
        self.manager.refresh_from_db()
        self.assertTrue(self.manager.check_password("Correct-pass-123"))
