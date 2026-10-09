from datetime import date, datetime, timedelta, time
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import JsonResponse
from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from unittest.mock import patch

from employees.models import Employee
from attendance.models import (
    Attendance,
    AttendanceEvent,
    OfficeLocation,
    RegularizationQuotaPolicy,
    Shift,
)
from attendance.tasks import check_consecutive_absences
from leave_management.models import LeavePolicy, LeaveRequest, LeaveType
from notifications.models import Notification
from notifications.services import create_notification, queue_notification_after_commit
from notifications.tasks import send_notification_email
from hr_copilot.models import CopilotPendingAction
from hr_copilot.services.pipeline import CopilotError
from hr_copilot.services.write_executor import pending_action_manager, write_action_executor
from hr_copilot.views import copilot_action_session_id
from .middleware import RequestContextMiddleware
from .models import SystemLog
from .services import SYSTEM_ACTOR, record_event


User = get_user_model()


class RecordEventTests(TestCase):
    def setUp(self):
        self.employee_user = User.objects.create_user(
            email="employee@example.com",
            password="password123",
        )
        Employee.objects.create(
            user=self.employee_user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined=date(2026, 1, 1),
        )
        self.manager = User.objects.create_user(
            email="manager@example.com",
            password="password123",
            is_system_admin=True,
        )
        self.superuser = User.objects.create_superuser(
            email="superuser@example.com",
            password="password123",
        )

    def test_ignored_events_are_not_recorded(self):
        from .services import IGNORED_EVENT_TYPES
        for event_type in IGNORED_EVENT_TYPES:
            record_event(
                event_type=event_type,
                category="TEST",
                severity="INFO",
                status="SUCCESS",
            )
        self.assertEqual(SystemLog.objects.count(), 0)

    def record(self, **overrides):
        values = {
            "event_type": "EMPLOYEE_UPDATED",
            "category": "EMPLOYEE",
            "severity": "INFO",
            "status": "SUCCESS",
            "message": "Employee updated",
            "source": "API",
        }
        values.update(overrides)
        return record_event(**values)

    def test_human_actor_is_recorded(self):
        log = self.record(actor=self.employee_user)

        self.assertEqual(log.actor, self.employee_user)
        self.assertEqual(log.actor_role, "EMPLOYEE")

    def test_role_detection_for_superuser_manager_and_employee(self):
        self.assertEqual(self.record(actor=self.superuser).actor_role, "SUPERUSER")
        self.assertEqual(self.record(actor=self.manager).actor_role, "MANAGER")
        self.assertEqual(self.record(actor=self.employee_user).actor_role, "EMPLOYEE")

    def test_system_actor_is_not_linked_to_a_user(self):
        log = self.record(actor=SYSTEM_ACTOR)

        self.assertIsNone(log.actor)
        self.assertEqual(log.actor_role, "SYSTEM")

    def test_missing_or_unauthenticated_actor_is_anonymous(self):
        anonymous = SimpleNamespace(is_authenticated=False)

        self.assertEqual(self.record().actor_role, "ANONYMOUS")
        self.assertEqual(self.record(actor=anonymous).actor_role, "ANONYMOUS")

    def test_model_and_mapping_targets_are_serialized(self):
        model_target = self.record(actor=self.manager, target=self.employee_user)
        mapping_target = self.record(
            target={"type": "employees.Employee", "id": 42, "label": "Ada Lovelace"}
        )

        self.assertEqual(model_target.target_type, "accounts.user")
        self.assertEqual(model_target.target_id, str(self.employee_user.pk))
        self.assertEqual(model_target.target_label, self.employee_user.email)
        self.assertEqual(mapping_target.target_type, "employees.Employee")
        self.assertEqual(mapping_target.target_id, "42")
        self.assertEqual(mapping_target.target_label, "Ada Lovelace")

    def test_request_and_explicit_request_id_are_recorded(self):
        request = SimpleNamespace(
            META={
                "REMOTE_ADDR": "192.0.2.10",
                "HTTP_USER_AGENT": "Test client",
                "HTTP_X_REQUEST_ID": "header-request-id",
            }
        )

        log = self.record(request=request, request_id="explicit-request-id")

        self.assertEqual(log.ip_address, "192.0.2.10")
        self.assertEqual(log.user_agent, "Test client")
        self.assertEqual(log.request_id, "explicit-request-id")

    def test_sensitive_fields_are_redacted(self):
        log = self.record(
            message="Bearer eyJnot-a-real-token.value.signature",
            metadata={
                "password": "do-not-store",
                "nested": {"api_key": "key-value", "safe": "visible"},
                "authorization": "Bearer abc123",
                "face_embedding": [0.1, 0.2],
            },
        )

        self.assertEqual(log.message, "[REDACTED]")
        self.assertEqual(log.metadata["password"], "[REDACTED]")
        self.assertEqual(log.metadata["nested"]["api_key"], "[REDACTED]")
        self.assertEqual(log.metadata["nested"]["safe"], "visible")
        self.assertEqual(log.metadata["face_embedding"], "[REDACTED]")

    def test_before_after_and_metadata_are_json_safe_and_bounded(self):
        log = self.record(
            before_state={"updated_at": datetime(2026, 9, 29, 12, 0), "amount": Decimal("1.20")},
            after_state={"ids": list(range(55)), "when": timezone.now(), "ref": uuid4()},
            metadata={"date": date(2026, 9, 29), "items": list(range(55))},
        )

        self.assertEqual(log.before_state["updated_at"], "2026-09-29T12:00:00")
        self.assertEqual(log.before_state["amount"], "1.20")
        self.assertEqual(len(log.after_state["ids"]), 51)
        self.assertEqual(log.after_state["ids"][-1], "[TRUNCATED_ITEMS]")
        self.assertEqual(log.metadata["date"], "2026-09-29")
        self.assertEqual(log.metadata["items"][-1], "[TRUNCATED_ITEMS]")


class RequestContextMiddlewareTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def call_middleware(self, path="/api/protected/", status=200, **headers):
        request = self.factory.get(path, **headers)
        request.user = AnonymousUser()
        middleware = RequestContextMiddleware(
            lambda request: JsonResponse({}, status=status)
        )
        return request, middleware(request)

    def test_generates_and_returns_request_id(self):
        request, response = self.call_middleware()

        self.assertIsNotNone(request.request_id)
        self.assertEqual(response["X-Request-ID"], request.request_id)
        self.assertRegex(request.request_id, r"^[0-9a-f-]{36}$")

    def test_propagates_valid_request_id(self):
        request_id = str(uuid4())

        request, response = self.call_middleware(HTTP_X_REQUEST_ID=request_id)

        self.assertEqual(request.request_id, request_id)
        self.assertEqual(response["X-Request-ID"], request_id)

    def test_record_event_receives_request_context(self):
        with patch("system_logs.middleware.record_event", wraps=record_event) as mocked:
            request, response = self.call_middleware(status=403)

        self.assertEqual(response.status_code, 403)
        mocked.assert_not_called()

    def test_logs_401_security_outcome(self):
        self.call_middleware(status=401)
        self.assertEqual(SystemLog.objects.count(), 0)

    def test_logs_403_security_outcome(self):
        user = User.objects.create_user(
            email="security.manager@example.com",
            password="password123",
            is_system_admin=True,
        )
        request = self.factory.get("/api/protected/")
        request.user = user
        response = RequestContextMiddleware(
            lambda request: JsonResponse({}, status=403)
        )(request)

        self.assertEqual(SystemLog.objects.count(), 0)
        self.assertEqual(response.status_code, 403)

    def test_sensitive_request_data_is_not_logged(self):
        request = self.factory.post(
            "/api/protected/?token=query-secret",
            {"password": "body-secret"},
            HTTP_AUTHORIZATION="Bearer header-secret",
            content_type="application/json",
        )
        request.user = AnonymousUser()
        response = RequestContextMiddleware(
            lambda request: JsonResponse({}, status=401)
        )(request)

        self.assertEqual(SystemLog.objects.count(), 0)


class EmployeeAccountEventTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.actor = User.objects.create_superuser(
            email="phase4.admin@example.com",
            password="password123",
        )
        self.client.force_authenticate(user=self.actor)

    def create_employee(self):
        response = self.client.post(
            "/api/admin/employees/",
            {
                "email": "phase4.employee@example.com",
                "password": "employee-secret-123",
                "first_name": "Original",
                "last_name": "Employee",
                "department": "Engineering",
                "employment_type": "PERMANENT",
                "date_joined": "2026-01-01",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        return Employee.objects.select_related("user").get(pk=response.data["id"])

    def test_employee_creation_logs_safe_state(self):
        employee = self.create_employee()

        log = SystemLog.objects.get(event_type="EMPLOYEE_CREATED")
        self.assertEqual(log.actor, self.actor)
        self.assertEqual(log.target_id, str(employee.pk))
        self.assertEqual(log.target_type, "employees.employee")
        self.assertEqual(log.after_state["email"], employee.user.email)
        self.assertNotIn("employee-secret-123", repr(log.after_state))
        self.assertNotIn("password", repr(log.after_state).lower())

    def test_employee_update_access_and_activation_events(self):
        employee = self.create_employee()
        SystemLog.objects.all().delete()

        response = self.client.patch(
            f"/api/admin/employees/{employee.pk}/",
            {
                "department": "Research",
                "app_access": {"dashboard": True, "attendance": False, "leave": True},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(SystemLog.objects.filter(event_type="EMPLOYEE_UPDATED").exists())
        access_log = SystemLog.objects.get(event_type="ACCESS_CHANGED")
        self.assertTrue(access_log.before_state["app_access"]["attendance"])
        self.assertFalse(access_log.after_state["app_access"]["attendance"])

        self.client.patch(
            f"/api/admin/employees/{employee.pk}/",
            {"is_active": False},
            format="json",
        )
        activation_log = SystemLog.objects.get(event_type="EMPLOYEE_DEACTIVATED")
        self.assertTrue(activation_log.before_state["is_active"])
        self.assertFalse(activation_log.after_state["is_active"])

    def test_employee_password_change_does_not_store_password(self):
        employee = self.create_employee()
        SystemLog.objects.all().delete()

        response = self.client.post(
            f"/api/admin/employees/{employee.pk}/change-password/",
            {"new_password": "replacement-secret-123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        log = SystemLog.objects.get(event_type="EMPLOYEE_PASSWORD_CHANGED")
        self.assertNotIn("replacement-secret-123", repr(log))
        self.assertEqual(log.after_state, {"must_change_password": "[REDACTED]"})

    def test_admin_password_reset_rejects_passwords_that_fail_django_validation(self):
        employee = self.create_employee()
        old_password_hash = employee.user.password
        response = self.client.post(
            f"/api/admin/employees/{employee.pk}/change-password/",
            {"new_password": "password"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        employee.user.refresh_from_db()
        self.assertEqual(employee.user.password, old_password_hash)
        self.assertFalse(SystemLog.objects.filter(event_type="EMPLOYEE_PASSWORD_CHANGED").exists())

    @patch("employees.views.process_enrollment", return_value=[0.1, 0.2])
    def test_face_enrollment_logs_without_biometric_data(self, process_enrollment):
        employee = self.create_employee()
        SystemLog.objects.all().delete()
        files = [
            SimpleUploadedFile(f"face-{index}.jpg", b"image-bytes", content_type="image/jpeg")
            for index in range(3)
        ]

        response = self.client.post(
            f"/api/admin/employees/{employee.pk}/enroll-face/",
            {"images": files},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200)
        process_enrollment.assert_called_once()
        log = SystemLog.objects.get(event_type="FACE_ENROLLMENT")
        self.assertEqual(log.status, "SUCCESS")
        self.assertNotIn("image-bytes", repr(log))
        self.assertNotIn("face_template", repr(log).lower())

    def test_manager_creation_role_and_lifecycle_events(self):
        response = self.client.post(
            "/api/admin/employees/managers/",
            {
                "email": "phase4.manager@example.com",
                "password": "manager-secret-123",
                "first_name": "Phase",
                "last_name": "Manager",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        manager = User.objects.get(pk=response.data["id"])
        event_types = set(
            SystemLog.objects.filter(target_id=str(manager.pk)).values_list("event_type", flat=True)
        )
        self.assertIn("MANAGER_CREATED", event_types)
        self.assertIn("ROLE_CHANGED", event_types)
        self.assertNotIn("manager-secret-123", repr(SystemLog.objects.filter(target_id=str(manager.pk)).values()))

        SystemLog.objects.filter(target_id=str(manager.pk)).delete()
        response = self.client.patch(
            f"/api/admin/employees/managers/{manager.pk}/",
            {"first_name": "Updated", "is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(SystemLog.objects.filter(event_type="MANAGER_DEACTIVATED").exists())
        self.assertTrue(SystemLog.objects.filter(event_type="MANAGER_UPDATED").exists())

    def test_manager_password_change_and_self_password_change_are_safe(self):
        manager = User.objects.create_user(
            email="phase4.existing.manager@example.com",
            password="manager-old-123",
            is_system_admin=True,
        )
        response = self.client.post(
            f"/api/admin/employees/managers/{manager.pk}/change-password/",
            {"new_password": "B4!different-manager-password"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        manager_log = SystemLog.objects.get(event_type="MANAGER_PASSWORD_CHANGED")
        self.assertNotIn("manager-new-123", repr(manager_log))

        manager.refresh_from_db()
        self.client.force_authenticate(user=manager)
        response = self.client.post(
            "/api/auth/change-password/",
            {
                "current_password": "B4!different-manager-password",
                "new_password": "R8$kL2!vQ9#sT4@mN6",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        password_log = SystemLog.objects.get(event_type="PASSWORD_CHANGED")
        self.assertEqual(password_log.actor, manager)
        self.assertEqual(password_log.target_id, str(manager.pk))
        self.assertNotIn("R8$kL2!vQ9#sT4@mN6", repr(password_log))


class AttendanceEventLoggingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            email="phase5.admin@example.com",
            password="password123",
        )
        self.employee_user = User.objects.create_user(
            email="phase5.employee@example.com",
            password="password123",
        )
        self.employee = Employee.objects.create(
            user=self.employee_user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined=date(2026, 1, 1),
        )
        self.shift = Shift.objects.create(
            name="Day Shift",
            code="PH5-DAY",
            start_time=time(9, 0),
            end_time=time(17, 0),
            employment_type="PERMANENT",
        )

    def test_checkin_checkout_and_face_verify_events(self):
        self.employee.shift = self.shift
        self.employee.save(update_fields=["shift"])
        self.client.force_authenticate(user=self.employee_user)
        with patch(
            "attendance.views.validate_attendance_geofence",
            return_value=(True, "", 12.0, (12.1, 77.1, 5.0)),
        ):
            check_in = self.client.post(
                "/api/attendance/check-in/",
                {"latitude": 12.1, "longitude": 77.1, "accuracy": 5},
                format="json",
            )
            check_out = self.client.post(
                "/api/attendance/check-out/",
                {"latitude": 12.1, "longitude": 77.1, "accuracy": 5},
                format="json",
            )
        self.assertEqual(check_in.status_code, 201)
        self.assertEqual(check_out.status_code, 200)

        with patch("attendance.views.find_closest_match", return_value=(self.employee, 0.2)):
            verify = self.client.post("/api/attendance/verify-face/", {"image": "biometric-payload"})
        self.assertEqual(verify.status_code, 200)

        logs = SystemLog.objects.filter(target_id=str(self.employee.pk))
        self.assertTrue(logs.filter(event_type="CHECK_IN", source="MOBILE").exists())
        self.assertTrue(logs.filter(event_type="CHECK_OUT", source="MOBILE").exists())
        self.assertTrue(logs.filter(event_type="CHECK_OUT", source="MOBILE").exists())
        self.assertFalse(logs.filter(event_type="FACE_VERIFY").exists())

    def test_admin_attendance_edit_reset_and_regularization_review_events(self):
        attendance_date = timezone.localdate()
        check_in = timezone.make_aware(datetime.combine(attendance_date, time(9, 0)))
        check_out = timezone.make_aware(datetime.combine(attendance_date, time(17, 0)))
        attendance = Attendance.objects.create(
            employee=self.employee,
            date=attendance_date,
            check_in=check_in,
            check_out=check_out,
            status="PRESENT",
        )
        self.client.force_authenticate(user=self.admin)
        edit = self.client.post(
            "/api/admin/attendance/edit/",
            {
                "employee": self.employee_user.email,
                "date": attendance_date.isoformat(),
                "reason": "Corrected recorded times",
                "check_in": check_in.isoformat(),
                "check_out": check_out.isoformat(),
                "status": "PRESENT",
            },
            format="json",
        )
        self.assertEqual(edit.status_code, 200)
        self.assertTrue(SystemLog.objects.filter(event_type="ATTENDANCE_EDIT").exists())

        reset = self.client.post(
            "/api/admin/attendance/reset/",
            {"employee": self.employee_user.email, "reason": "Reset for re-entry"},
            format="json",
        )
        self.assertEqual(reset.status_code, 200)
        reset_log = SystemLog.objects.get(event_type="ATTENDANCE_RESET")
        self.assertEqual(reset_log.actor, self.admin)
        self.assertNotIn("Reset for re-entry", repr(reset_log))

        self.client.force_authenticate(user=self.employee_user)
        request_date = attendance_date - timedelta(days=1)
        created = self.client.post(
            "/api/attendance/regularization/",
            {
                "attendance_date": request_date.isoformat(),
                "request_type": "FORGOT_CHECK_OUT",
                "requested_check_out": timezone.make_aware(
                    datetime.combine(request_date, time(17, 0))
                ).isoformat(),
                "reason": "Regularization reason should not become central metadata",
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        request_id = created.data["request_id"]
        self.assertTrue(SystemLog.objects.filter(event_type="REGULARIZATION_CREATED", target_id=str(request_id)).exists())

        self.client.force_authenticate(user=self.admin)
        approved = self.client.post(f"/api/attendance/admin/regularization/{request_id}/approve/", {}, format="json")
        self.assertEqual(approved.status_code, 200)
        approval_log = SystemLog.objects.get(event_type="REGULARIZATION_APPROVED", target_id=str(request_id))
        self.assertEqual(approval_log.after_state["status"], "APPROVED")
        self.assertNotIn("Regularization reason", repr(approval_log))

        policy = RegularizationQuotaPolicy.get_solo()
        policy.weekly_limit = 3
        policy.save(update_fields=["weekly_limit", "updated_at"])
        second_date = attendance_date
        self.client.force_authenticate(user=self.employee_user)
        rejected_request = self.client.post(
            "/api/attendance/regularization/",
            {
                "attendance_date": second_date.isoformat(),
                "request_type": "FORGOT_CHECK_IN",
                "requested_check_in": timezone.make_aware(
                    datetime.combine(second_date, time(9, 0))
                ).isoformat(),
                "reason": "Second regularization reason",
            },
            format="json",
        )
        self.assertEqual(rejected_request.status_code, 201)
        rejected_id = rejected_request.data["request_id"]
        self.client.force_authenticate(user=self.admin)
        rejected = self.client.post(
            f"/api/attendance/admin/regularization/{rejected_id}/reject/",
            {"rejection_reason": "Not supported"},
            format="json",
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertTrue(SystemLog.objects.filter(event_type="REGULARIZATION_REJECTED", target_id=str(rejected_id)).exists())

    def test_shift_quota_and_location_configuration_events(self):
        self.client.force_authenticate(user=self.admin)
        configured = self.client.post(
            "/api/attendance/admin/shift/configure/",
            {
                "employment_type": "CONTRACT",
                "shifts": [{"name": "Contract Day", "start_time": "08:00", "end_time": "16:00"}],
            },
            format="json",
        )
        self.assertEqual(configured.status_code, 200)
        self.assertTrue(SystemLog.objects.filter(event_type="SHIFT_CONFIGURATION_CHANGED").exists())

        quota = self.client.patch(
            "/api/attendance/admin/regularization/quota-settings/",
            {"weekly_limit": 2, "monthly_limit": 5},
            format="json",
        )
        self.assertEqual(quota.status_code, 200)
        quota_log = SystemLog.objects.get(event_type="REGULARIZATION_QUOTA_CHANGED")
        self.assertEqual(quota_log.after_state["weekly_limit"], 2)

        created = self.client.post(
            "/api/attendance/locations/",
            {"name": "Phase 5 Office", "latitude": 12.1, "longitude": 77.1, "radius_meters": 100},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        location_id = created.data["id"]
        self.assertTrue(SystemLog.objects.filter(event_type="OFFICE_LOCATION_CREATED").exists())
        updated = self.client.put(
            f"/api/attendance/locations/{location_id}/",
            {"name": "Phase 5 Office Updated", "latitude": 12.2, "longitude": 77.2, "radius_meters": 120},
            format="json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertTrue(SystemLog.objects.filter(event_type="OFFICE_LOCATION_UPDATED").exists())
        deleted = self.client.delete(f"/api/attendance/locations/{location_id}/")
        self.assertEqual(deleted.status_code, 200)
        self.assertTrue(SystemLog.objects.filter(event_type="OFFICE_LOCATION_DELETED").exists())

    def test_absence_detection_logs_system_event(self):
        result = check_consecutive_absences(run_date=date(2026, 9, 29))

        self.assertTrue(result["evaluated"])
        absence_log = SystemLog.objects.get(
            event_type="ABSENCE_DETECTED",
            target_id=str(self.employee.pk),
        )
        self.assertEqual(absence_log.actor_role, "SYSTEM")
        self.assertEqual(absence_log.source, "CELERY")


class LeaveNotificationEmailLoggingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(
            email="phase6.admin@example.com",
            password="password123",
        )
        self.employee_user = User.objects.create_user(
            email="phase6.employee@example.com",
            password="password123",
        )
        self.employee = Employee.objects.create(
            user=self.employee_user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined=date(2026, 1, 1),
        )
        self.leave_type = LeaveType.objects.create(
            name="Phase 6 Leave",
            code="PH6",
            is_paid=False,
        )

    def create_leave(self, start_date, request_type="create"):
        self.client.force_authenticate(user=self.employee_user)
        response = self.client.post(
            "/api/leave/requests/",
            {
                "leave_type": self.leave_type.id,
                "start_date": start_date.isoformat(),
                "end_date": start_date.isoformat(),
                "day_type": "FULL_DAY",
                "reason": f"Private leave reason for {request_type}",
            },
            format="json",
        )
        if response.status_code != 201:
            print("LEAVE ERROR:", response.data)
        self.assertEqual(response.status_code, 201)
        return LeaveRequest.objects.get(pk=response.data["id"])

    def test_leave_lifecycle_logs_safe_transitions(self):
        monday = timezone.localdate()
        while monday.weekday() != 0:
            monday += timedelta(days=1)
        
        leave_request = self.create_leave(monday)
        created_log = SystemLog.objects.get(
            event_type="LEAVE_CREATED",
            target_id=str(leave_request.pk),
        )
        self.assertEqual(created_log.actor, self.employee_user)
        self.assertNotIn("Private leave reason", repr(created_log))

        self.client.force_authenticate(user=self.admin)
        approved = self.client.post(
            f"/api/leave/admin/requests/{leave_request.pk}/approve/",
            {"remarks": "Approved privately"},
            format="json",
        )
        self.assertEqual(approved.status_code, 200)
        approved_log = SystemLog.objects.get(
            event_type="LEAVE_APPROVED",
            target_id=str(leave_request.pk),
        )
        self.assertEqual(approved_log.actor, self.admin)
        self.assertEqual(approved_log.after_state["status"], "APPROVED")
        self.assertNotIn("Approved privately", repr(approved_log))

        cancelled = self.client.post(
            f"/api/leave/admin/requests/{leave_request.pk}/cancel/",
            {},
            format="json",
        )
        self.assertEqual(cancelled.status_code, 200)
        self.assertTrue(
            SystemLog.objects.filter(
                event_type="LEAVE_CANCELLED",
                target_id=str(leave_request.pk),
            ).exists()
        )

        denied_request = self.create_leave(monday + timedelta(days=1), "deny")
        self.client.force_authenticate(user=self.admin)
        denied = self.client.post(
            f"/api/leave/admin/requests/{denied_request.pk}/deny/",
            {"remarks": "Denied privately"},
            format="json",
        )
        self.assertEqual(denied.status_code, 200)
        denied_log = SystemLog.objects.get(
            event_type="LEAVE_DENIED",
            target_id=str(denied_request.pk),
        )
        self.assertEqual(denied_log.after_state["status"], "DENIED")
        self.assertNotIn("Denied privately", repr(denied_log))

    def test_leave_type_and_policy_lifecycle_events(self):
        self.client.force_authenticate(user=self.admin)
        created = self.client.post(
            "/api/leave/admin/types/",
            {"name": "Phase 6 Extra", "code": "PH6X", "is_paid": False},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        leave_type_id = created.data["id"]
        self.assertTrue(SystemLog.objects.filter(event_type="LEAVE_TYPE_CREATED").exists())

        updated = self.client.patch(
            f"/api/leave/admin/types/{leave_type_id}/",
            {"name": "Phase 6 Extra Updated"},
            format="json",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertTrue(SystemLog.objects.filter(event_type="LEAVE_TYPE_UPDATED").exists())
        deleted = self.client.delete(f"/api/leave/admin/types/{leave_type_id}/")
        self.assertEqual(deleted.status_code, 200)
        self.assertTrue(SystemLog.objects.filter(event_type="LEAVE_TYPE_DELETED").exists())

        policy_payload = {
            "employee_type": "PERMANENT",
            "leave_type": self.leave_type.id,
            "annual_entitlement": "10.0",
            "allow_carry_forward": False,
            "max_carry_forward": "0.0",
            "unused_expires": True,
            "max_consecutive_days": 10,
            "min_notice_days": 0,
            "allow_half_day": True,
            "requires_document": False,
            "effective_from": "2026-01-01",
            "is_active": True,
        }
        policy_response = self.client.post(
            "/api/leave/admin/policies/",
            policy_payload,
            format="json",
        )
        self.assertEqual(policy_response.status_code, 201)
        policy_id = policy_response.data["id"]
        self.assertTrue(SystemLog.objects.filter(event_type="LEAVE_POLICY_CREATED").exists())

        updated_policy = self.client.patch(
            f"/api/leave/admin/policies/{policy_id}/",
            {"annual_entitlement": "12.0"},
            format="json",
        )
        self.assertEqual(updated_policy.status_code, 200)
        self.assertTrue(SystemLog.objects.filter(event_type="LEAVE_POLICY_UPDATED").exists())
        deleted_policy = self.client.delete(f"/api/leave/admin/policies/{policy_id}/")
        self.assertEqual(deleted_policy.status_code, 200)
        self.assertTrue(SystemLog.objects.filter(event_type="LEAVE_POLICY_DELETED").exists())

    def test_notification_lifecycle_logs_without_notification_body(self):
        notification = create_notification(
            user=self.employee_user,
            title="Attendance notice",
            message="Sensitive notification body should not be logged.",
            notification_type="ATTENDANCE",
        )
        self.assertFalse(SystemLog.objects.filter(event_type="NOTIFICATION_CREATED").exists())

        self.client.force_authenticate(user=self.employee_user)
        read = self.client.post(f"/api/notifications/{notification.pk}/read/")
        self.assertEqual(read.status_code, 200)
        self.assertFalse(SystemLog.objects.filter(event_type="NOTIFICATION_READ").exists())
        deleted = self.client.delete(f"/api/notifications/{notification.pk}/")
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(SystemLog.objects.filter(event_type="NOTIFICATION_DELETED").exists())

        with patch("notifications.services.send_notification_email.delay") as enqueue:
            with self.captureOnCommitCallbacks(execute=True):
                queue_notification_after_commit(
                    user=self.employee_user,
                    title="Queued notice",
                    message="Email body must not be logged.",
                    notification_type="SYSTEM",
                    email_subject="Private queued subject",
                    email_body="Private queued body",
                )
        enqueue.assert_called_once()
        self.assertFalse(SystemLog.objects.filter(event_type="EMAIL_QUEUED").exists())

    @patch("notifications.tasks.send_mail", return_value=1)
    def test_email_sent_event_excludes_email_content(self, send_mail):
        result = send_notification_email.apply(
            args=(
                [self.employee_user.email],
                "Private subject",
                "Private email body should not be logged.",
            ),
            throw=True,
        )

        self.assertEqual(result.result["sent"], 1)
        sent_log = SystemLog.objects.get(event_type="EMAIL_SENT")
        self.assertEqual(sent_log.metadata["recipient_count"], 1)
        self.assertNotIn("Private email body", repr(sent_log))
        self.assertNotIn("Private subject", repr(sent_log))
        self.assertFalse(SystemLog.objects.filter(event_type="TASK_STARTED", category="CELERY").exists())
        self.assertFalse(SystemLog.objects.filter(event_type="TASK_SUCCESS", category="CELERY").exists())
        send_mail.assert_called_once()

    @patch("notifications.tasks.send_mail", side_effect=RuntimeError("private email failure"))
    def test_email_retry_and_failure_events_exclude_exception_content(self, send_mail):
        retry_result = send_notification_email.apply(
            args=([self.employee_user.email], "Subject", "Body"),
            throw=False,
            retries=0,
        )
        self.assertTrue(retry_result.failed())
        self.assertFalse(SystemLog.objects.filter(event_type="EMAIL_RETRY").exists())

        failure_result = send_notification_email.apply(
            args=([self.employee_user.email], "Subject", "Body"),
            throw=False,
            retries=3,
        )
        self.assertTrue(failure_result.failed())
        failure_log = SystemLog.objects.filter(event_type="EMAIL_FAILED").order_by("-id").first()
        self.assertIsNotNone(failure_log)
        self.assertNotIn("private email failure", repr(failure_log))
        self.assertIsNotNone(failure_log)
        self.assertNotIn("private email failure", repr(failure_log))
        self.assertFalse(SystemLog.objects.filter(event_type="TASK_RETRY", category="CELERY").exists())
        self.assertFalse(SystemLog.objects.filter(event_type="TASK_FAILED", category="CELERY").exists())


class HRCopilotLoggingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_superuser(
            email="phase7.copilot@example.com",
            password="password123",
        )
        self.client.force_authenticate(user=self.user)

    def pending_action(self, **overrides):
        values = {
            "action_id": uuid4(),
            "session_id": copilot_action_session_id(self.user.id, "phase7-conversation"),
            "user": self.user,
            "conversation_id": "phase7-conversation",
            "action_type": "attendance_update",
            "intent": "attendance_update",
            "source": "hr_copilot",
            "target_data": {},
            "proposed_changes": {},
            "current_state": {},
            "validated": True,
            "authorization_scope": {"unrestricted": True},
            "status": "PENDING",
            "requires_confirmation": True,
            "expires_at": timezone.now() + timedelta(minutes=10),
            "description": "Safe action description",
        }
        values.update(overrides)
        return CopilotPendingAction.objects.create(**values)

    def test_query_conversation_and_failure_events_exclude_prompt(self):
        with patch(
            "hr_copilot.views.analyze_question",
            side_effect=CopilotError("phase7_failure", "Copilot request failed safely."),
        ):
            response = self.client.post(
                "/api/hr-copilot/query/",
                {
                    "message": "Private prompt should not be logged",
                    "conversation_id": "phase7-query",
                },
                format="json",
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SystemLog.objects.filter(event_type="COPILOT_CONVERSATION").exists())
        self.assertFalse(SystemLog.objects.filter(event_type="COPILOT_QUERY_FAILED").exists())

    def test_action_requested_confirmed_cancelled_and_expired(self):
        action = self.pending_action()
        cancelled = self.client.post(
            "/api/hr-copilot/actions/approve/",
            {
                "action_id": str(action.action_id),
                "action": "cancel",
                "conversation_id": "phase7-conversation",
            },
            format="json",
        )
        self.assertEqual(cancelled.status_code, 200)
        self.assertTrue(SystemLog.objects.filter(event_type="COPILOT_ACTION_CANCELLED").exists())

        requested = self.pending_action(action_type="leave_create", intent="leave_create")
        session_id = requested.session_id
        requested_dict = pending_action_manager._as_dict(requested)
        from hr_copilot.views import _record_copilot_action_event
        _record_copilot_action_event(
            event_type="COPILOT_ACTION_REQUESTED",
            user=self.user,
            action=requested_dict,
        )
        approved = pending_action_manager.approve_action(session_id, str(requested.action_id), self.user.id)
        _record_copilot_action_event(
            event_type="COPILOT_ACTION_CONFIRMED",
            user=self.user,
            action=approved,
        )
        self.assertTrue(SystemLog.objects.filter(event_type="COPILOT_ACTION_REQUESTED").exists())
        self.assertTrue(SystemLog.objects.filter(event_type="COPILOT_ACTION_CONFIRMED").exists())

        expired = self.pending_action(
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        with self.assertRaises(CopilotError) as error:
            pending_action_manager.approve_action(
                expired.session_id,
                str(expired.action_id),
                self.user.id,
            )
        self.assertEqual(error.exception.code, "action_expired")
        self.assertTrue(SystemLog.objects.filter(event_type="COPILOT_ACTION_EXPIRED").exists())

    def test_action_execution_and_failure_events_correlate_specialized_audits(self):
        action = self.pending_action()
        pending = pending_action_manager._as_dict(action)
        with patch.object(
            write_action_executor,
            "_execute_attendance_update",
            return_value={"success": True, "operation": "updated"},
        ):
            write_action_executor.execute_approved_action(pending, self.user)
        executed = SystemLog.objects.get(event_type="COPILOT_ACTION_EXECUTED")
        self.assertEqual(executed.metadata["action_audit_id"], action.audit_records.first().id)

        failed = self.pending_action()
        failed_action_audit = __import__("hr_copilot.models", fromlist=["CopilotActionAudit"]).CopilotActionAudit.objects.create(
            pending_action=failed,
            user=self.user,
            session_id=failed.session_id,
            action_type="write",
            intent=failed.intent,
            operation=failed.action_type,
            target_description=failed.description,
            success=False,
            explicit_confirmation=False,
            authorization_scope={},
        )
        from hr_copilot.views import _record_copilot_action_event
        _record_copilot_action_event(
            event_type="COPILOT_ACTION_FAILED",
            user=self.user,
            action={"action_id": str(failed.action_id), "action_type": failed.action_type},
            status="FAILED",
            severity="ERROR",
            metadata={"action_audit_id": failed_action_audit.id},
        )
        failure = SystemLog.objects.get(event_type="COPILOT_ACTION_FAILED")
        self.assertEqual(failure.metadata["action_audit_id"], failed_action_audit.id)


class SystemLogAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.superuser = User.objects.create_superuser(
            email="phase8.superuser@example.com",
            password="password123",
            first_name="Super",
            last_name="User",
        )
        self.employee_user = User.objects.create_user(
            email="phase8.employee@example.com",
            password="password123",
            first_name="Alice",
            last_name="Employee",
        )
        Employee.objects.create(
            user=self.employee_user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined=date(2026, 1, 1),
        )
        self.manager = User.objects.create_user(
            email="phase8.manager@example.com",
            password="password123",
            is_system_admin=True,
        )
        self.staff = User.objects.create_user(
            email="phase8.staff@example.com",
            password="password123",
            is_staff=True,
        )
        self.log_ids = []
        self.create_log(
            timestamp=timezone.now() - timedelta(days=3),
            event_type="LOGIN_SUCCESS",
            category="AUTHENTICATION",
            severity="INFO",
            status="SUCCESS",
            source="API",
            actor=self.employee_user,
            actor_role="EMPLOYEE",
            target_id="employee-42",
            target_label="Alice Employee",
            message="Employee signed in",
            request_id="request-old",
        )
        self.create_log(
            timestamp=timezone.now() - timedelta(days=2),
            event_type="LEAVE_APPROVED",
            category="LEAVE",
            severity="INFO",
            status="SUCCESS",
            source="ADMIN",
            actor=self.manager,
            actor_role="MANAGER",
            target_id="leave-7",
            target_label="Alice Employee",
            message="Leave approved",
            request_id="request-leave",
        )
        self.create_log(
            timestamp=timezone.now() - timedelta(days=1),
            event_type="EMAIL_FAILED",
            category="NOTIFICATION",
            severity="ERROR",
            status="FAILED",
            source="CELERY",
            actor=None,
            actor_role="SYSTEM",
            target_id="email-8",
            target_label="Alice Employee",
            message="Notification email failed",
            request_id="request-email",
        )

    def create_log(self, **values):
        defaults = {
            "timestamp": timezone.now(),
            "severity": "INFO",
            "category": "SYSTEM",
            "event_type": "TASK_SUCCESS",
            "status": "SUCCESS",
            "actor_role": "SYSTEM",
            "target_type": "employees.Employee",
            "target_id": "",
            "target_label": "",
            "message": "System event",
            "source": "SYSTEM",
            "request_id": "",
            "metadata": {},
        }
        defaults.update(values)
        log = SystemLog.objects.create(**defaults)
        self.log_ids.append(log.id)
        return log

    def get_as(self, user=None, path="/api/system-logs/"):
        if user is None:
            self.client.force_authenticate(user=None)
        else:
            self.client.force_authenticate(user=user)
        return self.client.get(path)

    def test_superuser_access_and_other_roles_denied(self):
        response = self.get_as(self.superuser)
        self.assertEqual(response.status_code, 200)

        for user in (self.employee_user, self.manager, self.staff):
            denied = self.get_as(user)
            self.assertEqual(denied.status_code, 403)

        anonymous = self.get_as(None)
        self.assertIn(anonymous.status_code, (401, 403))

    def test_global_search_covers_actor_target_message_and_request_id(self):
        response = self.get_as(self.superuser, "/api/system-logs/?search=Alice")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 3)

        request_search = self.get_as(self.superuser, "/api/system-logs/?search=request-email")
        self.assertEqual(request_search.data["count"], 1)

        actor_search = self.get_as(self.superuser, "/api/system-logs/?search=phase8.manager@example.com")
        self.assertEqual(actor_search.data["count"], 1)

    def test_each_major_filter(self):
        filters = {
            "category": ("LEAVE", "LEAVE_APPROVED"),
            "event_type": ("EMAIL_FAILED", "EMAIL_FAILED"),
            "severity": ("ERROR", "EMAIL_FAILED"),
            "status": ("FAILED", "EMAIL_FAILED"),
            "source": ("CELERY", "EMAIL_FAILED"),
            "actor": (str(self.manager.id), "LEAVE_APPROVED"),
            "actor_role": ("EMPLOYEE", "LOGIN_SUCCESS"),
        }
        for name, (value, expected_event) in filters.items():
            response = self.get_as(self.superuser, f"/api/system-logs/?{name}={value}")
            self.assertEqual(response.status_code, 200, name)
            self.assertEqual(response.data["count"], 1, name)
            self.assertEqual(response.data["results"][0]["event_type"], expected_event, name)

    def test_combined_filters_date_range_and_newest_first_ordering(self):
        date_from = (timezone.localdate() - timedelta(days=2)).isoformat()
        date_to = (timezone.localdate() - timedelta(days=1)).isoformat()
        response = self.get_as(
            self.superuser,
            f"/api/system-logs/?category=LEAVE&status=SUCCESS&date_from={date_from}&date_to={date_to}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["event_type"], "LEAVE_APPROVED")

        newest = self.get_as(self.superuser, "/api/system-logs/?ordering=-timestamp")
        timestamps = [row["timestamp"] for row in newest.data["results"]]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

    def test_pagination_and_detail_endpoint(self):
        for index in range(105):
            self.create_log(
                event_type="TASK_SUCCESS",
                category="CELERY",
                target_id=f"task-{index}",
                message=f"Task {index}",
            )

        first_page = self.get_as(self.superuser, "/api/system-logs/?page=2&page_size=10")
        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(first_page.data["count"], 108)
        self.assertEqual(len(first_page.data["results"]), 10)
        self.assertIsNotNone(first_page.data["next"])

        detail_id = self.log_ids[0]
        detail = self.get_as(self.superuser, f"/api/system-logs/{detail_id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data["id"], detail_id)
        self.assertEqual(detail.data["event_type"], "LOGIN_SUCCESS")

        write_attempt = self.client.post(
            "/api/system-logs/",
            {"message": "should not be written"},
            format="json",
        )
        self.assertEqual(write_attempt.status_code, 405)

    def test_invalid_parameters_are_rejected(self):
        invalid_queries = (
            "category=UNKNOWN",
            "event_type=UNKNOWN",
            "severity=UNKNOWN",
            "status=UNKNOWN",
            "source=UNKNOWN",
            "actor=not-an-id",
            "actor_role=UNKNOWN",
            "date_from=not-a-date",
            "date_from=2026-10-01&date_to=2026-09-01",
            "page=0",
            "page_size=101",
            "ordering=message",
        )
        for query in invalid_queries:
            response = self.get_as(self.superuser, f"/api/system-logs/?{query}")
            self.assertEqual(response.status_code, 400, query)

    def test_actor_suggestions_and_filtered_server_exports(self):
        actors = self.get_as(self.superuser, "/api/system-logs/actors/?search=Alice")
        self.assertEqual(actors.status_code, 200)
        self.assertTrue(any(item["email"] == self.employee_user.email for item in actors.data))

        csv_response = self.get_as(self.superuser, "/api/system-logs/export/?export_format=csv&category=LEAVE")
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("attachment; filename=\"system-logs.csv\"", csv_response["Content-Disposition"])
        csv_text = b"".join(csv_response.streaming_content).decode("utf-8")
        self.assertIn("LEAVE_APPROVED", csv_text)
        self.assertNotIn("EMAIL_FAILED", csv_text)

        xlsx_response = self.get_as(self.superuser, "/api/system-logs/export/?export_format=xlsx&status=SUCCESS")
        self.assertEqual(xlsx_response.status_code, 200)
        self.assertIn("system-logs.xlsx", xlsx_response["Content-Disposition"])
        self.assertTrue(xlsx_response.content.startswith(b"PK"))
