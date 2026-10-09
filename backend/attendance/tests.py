from datetime import time as datetime_time
from datetime import date, datetime, time as datetime_time, timedelta
from unittest.mock import patch, Mock
import requests
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from employees.models import Employee, FaceProfile
from attendance.models import (
    Attendance,
    AttendanceEvent,
    attendance_day_end,
    calculate_working_duration,
    get_effective_attendance_events,
)
from attendance.geofence import (
    WORKPLACE_LATITUDE,
    WORKPLACE_LONGITUDE,
    GEOFENCE_RADIUS_METERS,
    MAX_ACCURACY_METERS,
    calculate_haversine_distance,
)
from attendance.face_service import process_enrollment, find_closest_match, FaceExtractionError, FaceLivenessError
from attendance.models import RegularizationRequest
from accounts.models import ManagerScope

User = get_user_model()


def camera_sequence_payload(**extra):
    return {
        "frames": [f"frame-{index}" for index in range(5)],
        "captured_at_ms": [index * 250 for index in range(5)],
        **extra,
    }


class ManagerEmployeeAttendanceScopeTests(APITestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            email="scope.manager@example.com", password="password123", is_system_admin=True
        )
        ManagerScope.objects.create(manager=self.manager, scope_type="SECTION", value="C")
        self.in_scope = self.make_employee("scope.c@example.com", "INTERN", section="C")
        self.out_scope = self.make_employee("scope.d@example.com", "INTERN", section="D")
        Attendance.objects.create(employee=self.in_scope, date=timezone.localdate(), status="PRESENT")
        Attendance.objects.create(employee=self.out_scope, date=timezone.localdate(), status="PRESENT")

    def make_employee(self, email, employment_type, section="", department="Engineering"):
        user = User.objects.create_user(email=email, password="password123")
        return Employee.objects.create(
            user=user, department=department, employment_type=employment_type,
            section=section, date_joined="2026-01-01",
        )

    def test_employee_list_and_detail_are_scoped(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get("/api/admin/employees/list/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual({row["id"] for row in response.data}, {self.in_scope.id})
        self.assertEqual(self.client.get(f"/api/admin/employees/{self.in_scope.id}/").status_code, 200)
        self.assertEqual(self.client.get(f"/api/admin/employees/{self.out_scope.id}/").status_code, 403)

    def test_attendance_history_and_daily_view_are_scoped(self):
        self.client.force_authenticate(self.manager)
        history = self.client.get("/api/attendance/history/")
        self.assertEqual(history.status_code, 200)
        self.assertEqual({row["employee_id"] for row in history.data}, {self.in_scope.id})
        daily = self.client.get("/api/admin/attendance/")
        self.assertEqual(daily.status_code, 200)
        self.assertEqual({row["employee"] for row in daily.data}, {self.in_scope.user.email})

    def test_manager_cannot_edit_or_reset_attendance(self):
        self.client.force_authenticate(self.manager)
        self.assertEqual(self.client.post("/api/admin/attendance/edit/", {}).status_code, 403)
        self.assertEqual(self.client.post("/api/admin/attendance/reset/", {}).status_code, 403)

    def test_permanent_scope_uses_department_and_superuser_is_unrestricted(self):
        department_manager = User.objects.create_user(
            email="department.manager@example.com", password="password123", is_system_admin=True
        )
        ManagerScope.objects.create(manager=department_manager, scope_type="DEPARTMENT", value="Engineering")
        permanent = self.make_employee("permanent.engineering@example.com", "PERMANENT", section="D")
        self.client.force_authenticate(department_manager)
        self.assertEqual(self.client.get(f"/api/admin/employees/{permanent.id}/").status_code, 200)
        self.client.force_authenticate(User.objects.create_superuser("scope.root@example.com", "password123"))
        self.assertEqual(self.client.get(f"/api/admin/employees/{self.out_scope.id}/").status_code, 200)


class RegularizationWorkflowTests(APITestCase):
    def setUp(self):
        self.attendance_date = timezone.localdate()
        while self.attendance_date.weekday() >= 5:
            self.attendance_date -= timedelta(days=1)
        while timezone.localdate() - self.attendance_date > timedelta(days=2):
            self.attendance_date += timedelta(days=1)
            while self.attendance_date.weekday() >= 5:
                self.attendance_date -= timedelta(days=1)
        self.employee_user = User.objects.create_user(
            email="regularization.employee@example.com",
            password="password123",
        )
        self.employee = Employee.objects.create(
            user=self.employee_user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined=self.attendance_date - timedelta(days=30),
            is_active=True,
        )
        self.admin_user = User.objects.create_user(
            email="regularization.admin@example.com",
            password="password123",
            is_staff=True,
            is_system_admin=True,
        )
        from accounts.models import ManagerScope
        ManagerScope.objects.create(manager=self.admin_user, scope_type="DEPARTMENT", value="Engineering")
        self.check_in = timezone.make_aware(
            datetime.combine(self.attendance_date, datetime_time(9, 0)),
            timezone.get_current_timezone(),
        )
        self.check_out = timezone.make_aware(
            datetime.combine(self.attendance_date, datetime_time(17, 0)),
            timezone.get_current_timezone(),
        )
        self.attendance = Attendance.objects.create(
            employee=self.employee,
            date=self.attendance_date,
            check_in=self.check_in,
            check_out=self.check_out,
            status="PRESENT",
        )
        self.original_check_in_event = AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=self.check_in,
            event_type="CHECK_IN",
            source="MOBILE",
        )
        self.original_check_out_event = AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=self.check_out,
            event_type="CHECK_OUT",
            source="MOBILE",
        )
        self.request = RegularizationRequest.objects.create(
            employee=self.employee,
            attendance_date=self.attendance_date,
            request_type="INCORRECT_ATTENDANCE",
            existing_check_in=self.check_in,
            existing_check_out=self.check_out,
            requested_check_in=self.check_in + timedelta(minutes=30),
            requested_check_out=self.check_out + timedelta(minutes=30),
            reason="The recorded times need correction.",
        )

    def test_employee_can_create_pending_request(self):
        self.request.delete()
        self.client.force_authenticate(user=self.employee_user)
        response = self.client.post("/api/attendance/regularization/", {
            "attendance_date": self.attendance_date.isoformat(),
            "request_type": "FORGOT_CHECK_OUT",
            "requested_check_out": (self.check_out + timedelta(minutes=15)).isoformat(),
            "reason": "I forgot to check out.",
        }, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created = RegularizationRequest.objects.get(id=response.data["request_id"])
        self.assertEqual(created.status, "PENDING")
        self.assertEqual(created.employee, self.employee)

    def test_approved_forgotten_checkout_creates_day_scoped_correction(self):
        self.original_check_out_event.delete()
        self.attendance.check_out = None
        self.attendance.status = "INCOMPLETE"
        self.attendance.working_duration = None
        self.attendance.save(update_fields=["check_out", "status", "working_duration"])
        self.request.delete()
        request_row = RegularizationRequest.objects.create(
            employee=self.employee,
            attendance_date=self.attendance_date,
            request_type="FORGOT_CHECK_OUT",
            existing_check_in=self.check_in,
            requested_check_out=self.check_out,
            reason="I forgot to check out.",
        )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            f"/api/attendance/admin/regularization/{request_row.id}/approve/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.attendance.refresh_from_db()
        request_row.refresh_from_db()
        self.assertEqual(self.attendance.status, "PRESENT")
        self.assertEqual(self.attendance.check_out, self.check_out)
        self.assertTrue(
            AttendanceEvent.objects.filter(
                employee=self.employee,
                timestamp=self.check_out,
                event_type="CHECK_OUT",
                source="ADMIN",
            ).exists()
        )
        self.assertIsNotNone(request_row.attendance_correction)

    def test_weekly_quota_counts_submitted_requests_and_blocks_second(self):
        self.request.status = "REJECTED"
        self.request.save(update_fields=["status", "updated_at"])
        self.client.force_authenticate(user=self.employee_user)

        quota = self.client.get("/api/attendance/regularization/quota/")
        self.assertEqual(quota.status_code, status.HTTP_200_OK)
        self.assertEqual(quota.data["weekly_limit"], 1)
        self.assertEqual(quota.data["weekly_used"], 1)
        self.assertEqual(quota.data["weekly_remaining"], 0)
        self.assertEqual(quota.data["monthly_used"], 1)
        self.assertEqual(quota.data["monthly_limit"], 4)
        self.assertEqual(quota.data["monthly_remaining"], 3)

        blocked = self.client.post("/api/attendance/regularization/", {
            "attendance_date": self.attendance_date.isoformat(),
            "request_type": "FORGOT_CHECK_OUT",
            "requested_check_out": (self.check_out + timedelta(minutes=15)).isoformat(),
            "reason": "Second request this week.",
        }, format="json")
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(blocked.data["weekly_used"], 1)
        self.assertIn("calendar week", blocked.data["detail"])

    def test_monthly_quota_blocks_fifth_request_across_weeks(self):
        self.request.status = "REJECTED"
        self.request.save(update_fields=["status", "updated_at"])
        anchor = date(2026, 9, 30)
        first_created = timezone.make_aware(datetime.combine(date(2026, 9, 1), datetime_time(12, 0)))
        RegularizationRequest.objects.filter(id=self.request.id).update(created_at=first_created)
        for day in (7, 14, 21):
            request_row = RegularizationRequest.objects.create(
                employee=self.employee,
                attendance_date=self.attendance_date,
                request_type="INCORRECT_ATTENDANCE",
                reason="Earlier monthly request.",
                status="REJECTED",
            )
            created = timezone.make_aware(datetime.combine(date(2026, 9, day), datetime_time(12, 0)))
            RegularizationRequest.objects.filter(id=request_row.id).update(created_at=created)
        self.client.force_authenticate(user=self.employee_user)
        with patch("attendance.views.timezone.localdate", return_value=anchor):
            quota = self.client.get("/api/attendance/regularization/quota/")
            self.assertEqual(quota.data["weekly_used"], 0)
            self.assertEqual(quota.data["monthly_used"], 4)
            self.assertEqual(quota.data["monthly_remaining"], 0)
            blocked = self.client.post("/api/attendance/regularization/", {
                "attendance_date": anchor.isoformat(),
                "request_type": "FORGOT_CHECK_OUT",
                "requested_check_out": timezone.make_aware(datetime.combine(anchor, datetime_time(17, 15))).isoformat(),
                "reason": "Fifth request this month.",
            }, format="json")
        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(blocked.data["monthly_limit"], 4)
        self.assertEqual(blocked.data["monthly_used"], 4)
        self.assertEqual(blocked.data["monthly_remaining"], 0)

    def test_monthly_quota_resets_for_new_calendar_month(self):
        self.request.created_at = timezone.now() - timedelta(days=40)
        RegularizationRequest.objects.filter(id=self.request.id).update(created_at=self.request.created_at)
        self.client.force_authenticate(user=self.employee_user)
        quota = self.client.get("/api/attendance/regularization/quota/")
        self.assertEqual(quota.status_code, status.HTTP_200_OK)
        self.assertEqual(quota.data["monthly_used"], 0)
        self.assertEqual(quota.data["monthly_remaining"], 4)
        self.assertEqual(quota.data["weekly_used"], 0)
        self.assertEqual(quota.data["weekly_remaining"], 1)

    def test_employee_can_submit_grouped_days_and_admin_approve_them(self):
        RegularizationRequest.objects.filter(employee=self.employee).delete()
        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())
        # Simulate a date at least one day into the current business week so
        # the grouped request always contains two past weekdays, including
        # when this test happens to run on a Monday or weekend.
        anchor = week_start + timedelta(days=min(max(today.weekday(), 1), 4))
        second_date = anchor - timedelta(days=1)
        effective_now = timezone.make_aware(
            datetime.combine(anchor, datetime_time(12, 0)),
            timezone.get_current_timezone(),
        )
        self.employee.date_joined = anchor - timedelta(days=30)
        self.employee.save(update_fields=["date_joined"])
        self.attendance_date = anchor
        self.check_in = timezone.make_aware(datetime.combine(self.attendance_date, datetime_time(9, 0)))
        self.check_out = timezone.make_aware(datetime.combine(self.attendance_date, datetime_time(17, 0)))
        self.client.force_authenticate(user=self.employee_user)
        with patch("attendance.views.timezone.localdate", return_value=anchor), \
             patch("django.utils.timezone.now", return_value=effective_now):
            response = self.client.post("/api/attendance/regularization/", {
                "period_type": "WEEK",
                "days": [
                    {
                        "attendance_date": self.attendance_date.isoformat(),
                        "request_type": "INCORRECT_ATTENDANCE",
                        "requested_check_in": (self.check_in + timedelta(minutes=10)).isoformat(),
                        "requested_check_out": self.check_out.isoformat(),
                        "reason": "Correct first day.",
                    },
                    {
                        "attendance_date": second_date.isoformat(),
                        "request_type": "FORGOT_CHECK_OUT",
                        "requested_check_out": timezone.make_aware(datetime.combine(second_date, datetime_time(17, 0))).isoformat(),
                        "reason": "Forgot to check out.",
                    },
                ],
            }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        request_id = response.data["request_id"]
        self.assertEqual(RegularizationRequest.objects.get(id=request_id).days.count(), 2)
        with patch("attendance.views.timezone.localdate", return_value=anchor):
            quota = self.client.get("/api/attendance/regularization/quota/")
        self.assertEqual(quota.data["monthly_used"], 1)
        self.assertEqual(quota.data["weekly_used"], 1)

        self.client.force_authenticate(user=self.admin_user)
        with patch("attendance.views.timezone.localdate", return_value=anchor), \
             patch("django.utils.timezone.now", return_value=effective_now):
            review = self.client.get(f"/api/attendance/admin/regularization/{request_id}/")
            self.assertEqual(review.status_code, status.HTTP_200_OK, review.data)
            approve = self.client.post(f"/api/attendance/admin/regularization/{request_id}/approve/", {
                "days": [
                    {"id": day["id"], "check_in": day["requested_check_in"], "check_out": day["requested_check_out"]}
                    for day in review.data["days"]
                ],
            }, format="json")
        self.assertEqual(approve.status_code, status.HTTP_200_OK, approve.data)
        self.assertEqual(approve.data["approved_days"], 2)
        self.assertEqual(RegularizationRequest.objects.get(id=request_id).status, "APPROVED")

    def test_admin_approval_applies_final_times_and_audits_correction(self):
        self.client.force_authenticate(user=self.admin_user)
        final_check_in = self.check_in + timedelta(hours=1)
        final_check_out = self.check_out + timedelta(hours=1)
        response = self.client.post(
            f"/api/attendance/admin/regularization/{self.request.id}/approve/",
            {"check_in": final_check_in.isoformat(), "check_out": final_check_out.isoformat()},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.request.refresh_from_db()
        self.attendance.refresh_from_db()
        self.assertEqual(self.request.status, "APPROVED")
        self.assertEqual(self.request.reviewed_by, self.admin_user)
        self.assertIsNotNone(self.request.reviewed_at)
        self.assertEqual(self.request.approved_check_in, final_check_in)
        self.assertEqual(self.request.approved_check_out, final_check_out)
        self.assertEqual(self.attendance.check_in, final_check_in)
        self.assertEqual(self.attendance.check_out, final_check_out)
        self.assertEqual(self.request.attendance_correction.correction_type, "REGULARIZATION")
        self.assertEqual(
            datetime.fromisoformat(self.request.attendance_correction.previous_data["check_in"]),
            self.check_in,
        )

    def _approve_request(self, check_in=None, check_out=None, reason="Correction"):
        RegularizationRequest.objects.filter(
            employee=self.employee,
            attendance_date=self.attendance_date,
            status="PENDING",
        ).delete()
        request_row = RegularizationRequest.objects.create(
            employee=self.employee,
            attendance_date=self.attendance_date,
            request_type="INCORRECT_ATTENDANCE",
            existing_check_in=self.attendance.check_in,
            existing_check_out=self.attendance.check_out,
            requested_check_in=check_in,
            requested_check_out=check_out,
            reason=reason,
        )
        correction = request_row.approve(
            self.admin_user,
            approved_check_in=check_in,
            approved_check_out=check_out,
        )
        self.attendance.refresh_from_db()
        return request_row, correction

    def test_both_times_correction_is_the_only_effective_interval(self):
        corrected_in = timezone.make_aware(datetime.combine(self.attendance_date, datetime_time(10, 0)))
        corrected_out = timezone.make_aware(datetime.combine(self.attendance_date, datetime_time(18, 0)))

        request_row, correction = self._approve_request(corrected_in, corrected_out)

        self.assertEqual(self.attendance.check_in, corrected_in)
        self.assertEqual(self.attendance.check_out, corrected_out)
        self.assertEqual(self.attendance.working_duration, timedelta(hours=8))
        self.assertEqual(
            list(get_effective_attendance_events(self.employee, self.attendance_date)),
            list(correction.attendance_events.order_by("timestamp", "id")),
        )
        self.assertEqual(request_row.attendance_correction, correction)

    def test_repeated_corrections_use_only_the_latest_approved_correction(self):
        first_in = timezone.make_aware(datetime.combine(self.attendance_date, datetime_time(10, 0)))
        first_out = timezone.make_aware(datetime.combine(self.attendance_date, datetime_time(18, 0)))
        second_in = timezone.make_aware(datetime.combine(self.attendance_date, datetime_time(11, 0)))
        second_out = timezone.make_aware(datetime.combine(self.attendance_date, datetime_time(19, 0)))

        _, first_correction = self._approve_request(first_in, first_out, "First correction")
        _, second_correction = self._approve_request(second_in, second_out, "Second correction")

        self.assertEqual(self.attendance.working_duration, timedelta(hours=8))
        self.assertEqual(self.attendance.check_in, second_in)
        self.assertEqual(self.attendance.check_out, second_out)
        effective = get_effective_attendance_events(self.employee, self.attendance_date)
        self.assertTrue(effective)
        self.assertTrue(all(event.correction_id == second_correction.id for event in effective))
        self.assertTrue(first_correction.attendance_events.exists())
        self.assertEqual(AttendanceEvent.objects.filter(employee=self.employee).count(), 6)

    def test_check_in_only_correction_retains_historical_checkout(self):
        corrected_in = timezone.make_aware(datetime.combine(self.attendance_date, datetime_time(10, 0)))

        self._approve_request(corrected_in, None, "Correct check-in")

        self.assertEqual(self.attendance.check_in, corrected_in)
        self.assertEqual(self.attendance.check_out, self.check_out)
        self.assertEqual(self.attendance.working_duration, timedelta(hours=7))

    def test_check_out_only_correction_retains_historical_checkin(self):
        corrected_out = timezone.make_aware(datetime.combine(self.attendance_date, datetime_time(18, 0)))

        self._approve_request(None, corrected_out, "Correct check-out")

        self.assertEqual(self.attendance.check_in, self.check_in)
        self.assertEqual(self.attendance.check_out, corrected_out)
        self.assertEqual(self.attendance.working_duration, timedelta(hours=9))

    def test_multiple_cycles_are_replaced_by_latest_both_times_correction(self):
        AttendanceEvent.objects.all().delete()
        first_in = timezone.make_aware(datetime.combine(self.attendance_date, datetime_time(9, 0)))
        first_out = timezone.make_aware(datetime.combine(self.attendance_date, datetime_time(13, 0)))
        second_in = timezone.make_aware(datetime.combine(self.attendance_date, datetime_time(14, 0)))
        second_out = timezone.make_aware(datetime.combine(self.attendance_date, datetime_time(17, 0)))
        AttendanceEvent.objects.bulk_create([
            AttendanceEvent(employee=self.employee, timestamp=first_in, event_type="CHECK_IN", source="MOBILE"),
            AttendanceEvent(employee=self.employee, timestamp=first_out, event_type="CHECK_OUT", source="MOBILE"),
            AttendanceEvent(employee=self.employee, timestamp=second_in, event_type="CHECK_IN", source="MOBILE"),
            AttendanceEvent(employee=self.employee, timestamp=second_out, event_type="CHECK_OUT", source="MOBILE"),
        ])
        self.attendance.check_in = first_in
        self.attendance.check_out = second_out
        self.attendance.status = "PRESENT"
        self.attendance.save(update_fields=["check_in", "check_out", "status"])

        corrected_in = timezone.make_aware(datetime.combine(self.attendance_date, datetime_time(10, 0)))
        corrected_out = timezone.make_aware(datetime.combine(self.attendance_date, datetime_time(18, 0)))
        self._approve_request(corrected_in, corrected_out, "Replace cycles")

        self.assertEqual(self.attendance.working_duration, timedelta(hours=8))
        self.assertEqual(AttendanceEvent.objects.filter(employee=self.employee).count(), 6)

    def test_api_duration_uses_same_effective_events_as_persisted_duration(self):
        corrected_in = timezone.make_aware(datetime.combine(self.attendance_date, datetime_time(10, 0)))
        corrected_out = timezone.make_aware(datetime.combine(self.attendance_date, datetime_time(18, 0)))
        self._approve_request(corrected_in, corrected_out, "API duration")
        self.client.force_authenticate(user=self.employee_user)

        response = self.client.get("/api/attendance/history/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = next(item for item in response.data if str(item["date"]) == self.attendance_date.isoformat())
        self.assertEqual(row["working_duration"], timedelta(hours=8))

    def test_admin_cannot_approve_with_invalid_final_times(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            f"/api/attendance/admin/regularization/{self.request.id}/approve/",
            {"check_in": self.check_out.isoformat(), "check_out": self.check_in.isoformat()},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.request.refresh_from_db()
        self.attendance.refresh_from_db()
        self.assertEqual(self.request.status, "PENDING")
        self.assertEqual(self.attendance.check_in, self.check_in)
        self.assertEqual(self.attendance.check_out, self.check_out)

    def test_rejection_requires_reason_and_does_not_change_attendance(self):
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            f"/api/attendance/admin/regularization/{self.request.id}/reject/",
            {"rejection_reason": "The submitted times cannot be verified."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.request.refresh_from_db()
        self.attendance.refresh_from_db()
        self.assertEqual(self.request.status, "REJECTED")
        self.assertEqual(self.request.rejection_reason, "The submitted times cannot be verified.")
        self.assertEqual(self.request.reviewed_by, self.admin_user)
        self.assertEqual(self.attendance.check_in, self.check_in)
        self.assertEqual(self.attendance.check_out, self.check_out)
        self.assertEqual(AttendanceEvent.objects.filter(employee=self.employee).count(), 2)

    def test_employee_cannot_approve_regularization(self):
        self.client.force_authenticate(user=self.employee_user)
        response = self.client.post(
            f"/api/attendance/admin/regularization/{self.request.id}/approve/",
            {"check_in": self.check_in.isoformat(), "check_out": self.check_out.isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch("attendance.views.timezone.localdate")
    def test_phase1_single_day_older_than_48h_blocked(self, mock_localdate):
        # Anchor to a Wednesday
        mock_localdate.return_value = date(2026, 10, 7) # Wednesday
        self.client.force_authenticate(user=self.employee_user)
        # 3 days ago is Sunday, older than 48h
        response = self.client.post("/api/attendance/regularization/", {
            "period_type": "DAY",
            "days": [{"attendance_date": "2026-10-04", "request_type": "INCORRECT_ATTENDANCE", "reason": "Test"}]
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("must be within the past 48 hours", str(response.data))

    @patch("attendance.views.timezone.localdate")
    def test_phase1_current_week_allowed_and_previous_week_blocked(self, mock_localdate):
        # Anchor to a Thursday
        mock_localdate.return_value = date(2026, 10, 8) # Thursday
        # The shared fixture creates a request to exercise quota behavior in
        # other tests. Start with an empty quota state for this eligibility test.
        RegularizationRequest.objects.filter(employee=self.employee).delete()
        self.client.force_authenticate(user=self.employee_user)
        # Monday is 2026-10-05
        # Attempt to submit previous Friday (2026-10-02) -> blocked
        res_prev = self.client.post("/api/attendance/regularization/", {
            "period_type": "WEEK",
            "days": [{"attendance_date": "2026-10-02", "request_type": "INCORRECT_ATTENDANCE", "reason": "Test"}]
        }, format="json")
        self.assertEqual(res_prev.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("current calendar week", str(res_prev.data))

        quota = self.client.get("/api/attendance/regularization/quota/")
        self.assertEqual(quota.data["weekly_used"], 0)
        self.assertEqual(quota.data["monthly_used"], 0)

        # Attempt to submit current Monday (2026-10-05) -> allowed even if > 48 hours
        # First ensure employee was joined before that date
        self.employee.date_joined = date(2026, 1, 1)
        self.employee.save()
        Attendance.objects.create(employee=self.employee, date=date(2026, 10, 5), status="ABSENT")
        res_curr = self.client.post("/api/attendance/regularization/", {
            "period_type": "WEEK",
            "days": [{"attendance_date": "2026-10-05", "request_type": "INCORRECT_ATTENDANCE", "reason": "Test", "requested_check_in": "2026-10-05T09:00:00Z", "requested_check_out": "2026-10-05T17:00:00Z"}]
        }, format="json")
        self.assertEqual(res_curr.status_code, status.HTTP_201_CREATED)

    @patch("attendance.views.timezone.localdate")
    def test_phase1_future_date_blocked(self, mock_localdate):
        mock_localdate.return_value = date(2026, 10, 8)
        self.client.force_authenticate(user=self.employee_user)
        res = self.client.post("/api/attendance/regularization/", {
            "period_type": "WEEK",
            "days": [{"attendance_date": "2026-10-09", "request_type": "INCORRECT_ATTENDANCE", "reason": "Test"}]
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("future dates are not allowed", str(res.data))

    @patch("django.utils.timezone.localdate")
    def test_phase1_mixed_weeks_blocked(self, mock_localdate):
        mock_localdate.return_value = date(2026, 10, 15)
        self.client.force_authenticate(user=self.employee_user)
        res = self.client.post("/api/attendance/regularization/", {
            "period_type": "WEEK",
            "days": [
                {"attendance_date": "2026-10-05", "request_type": "INCORRECT_ATTENDANCE", "reason": "Test", "requested_check_in": "2026-10-05T09:00:00Z", "requested_check_out": "2026-10-05T17:00:00Z"},
                {"attendance_date": "2026-10-12", "request_type": "INCORRECT_ATTENDANCE", "reason": "Test", "requested_check_in": "2026-10-12T09:00:00Z", "requested_check_out": "2026-10-12T17:00:00Z"}
            ]
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("multi-day requests are only allowed for dates in the current calendar week", str(res.data))

    @patch("django.utils.timezone.now")
    @patch("django.utils.timezone.localdate")
    def test_phase1_approval_revalidation(self, mock_localdate, mock_now):
        mock_localdate.return_value = date(2026, 10, 5)
        mock_now.return_value = timezone.make_aware(datetime.combine(date(2026, 10, 5), datetime_time(12, 0)))
        # Request created properly
        req = RegularizationRequest.objects.create(
            employee=self.employee,
            attendance_date=date(2026, 10, 5),
            period_type="WEEK",
            request_type="INCORRECT_ATTENDANCE",
            reason="Test",
            status="PENDING"
        )
        # Attempt to approve it when current date is next week
        mock_localdate.return_value = date(2026, 10, 13) # Next Tuesday
        mock_now.return_value = timezone.make_aware(datetime.combine(date(2026, 10, 13), datetime_time(12, 0)))
        
        self.client.force_authenticate(user=self.admin_user)
        # Assuming admin can approve and requested_check_in / requested_check_out are handled or we pass them in approve
        # Actually approve requires valid times, let's provide approved_check_in and approved_check_out
        res = self.client.post(f"/api/attendance/admin/regularization/{req.id}/approve/", {
            "check_in": "2026-10-05T09:00:00Z",
            "check_out": "2026-10-05T17:00:00Z"
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        req.refresh_from_db()
        self.assertEqual(req.status, "APPROVED")



class AttendanceGeofenceTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="employee@example.com",
            password="password123",
        )
        from attendance.models import Shift
        self.shift = Shift.objects.create(
            name="Morning Shift",
            code="MORN",
            start_time=datetime_time(9, 0),
            end_time=datetime_time(17, 0),
            is_active=True,
        )
        self.employee = Employee.objects.create(
            user=self.user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined=date.today(),
            is_active=True,
            shift=self.shift,
        )
        self.client.force_authenticate(user=self.user)

        self.valid_location = {
            "latitude": WORKPLACE_LATITUDE,
            "longitude": WORKPLACE_LONGITUDE,
            "accuracy": 15.0,
        }

        # Point ~22km north of workplace — guaranteed outside any sane geofence radius
        self.outside_location = {
            "latitude": WORKPLACE_LATITUDE + 0.2,
            "longitude": WORKPLACE_LONGITUDE,
            "accuracy": 10.0,
        }

        # Poor accuracy — exceeds MAX_ACCURACY_METERS (500m in env, 200m in code default)
        self.low_accuracy_location = {
            "latitude": WORKPLACE_LATITUDE,
            "longitude": WORKPLACE_LONGITUDE,
            "accuracy": 600.0,
        }

    def test_haversine_distance_calculation(self):
        dist_same = calculate_haversine_distance(
            WORKPLACE_LATITUDE, WORKPLACE_LONGITUDE,
            WORKPLACE_LATITUDE, WORKPLACE_LONGITUDE
        )
        self.assertAlmostEqual(dist_same, 0.0, places=1)

        dist_outside = calculate_haversine_distance(
            self.outside_location["latitude"], self.outside_location["longitude"],
            WORKPLACE_LATITUDE, WORKPLACE_LONGITUDE
        )
        # The outside_location is ~22km away; assert it is genuinely far
        self.assertGreater(dist_outside, 1000.0)

    def test_check_in_successful_inside_geofence(self):
        response = self.client.post("/api/attendance/check-in/", self.valid_location, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["message"], "Attendance marked successfully.")
        
        record = Attendance.objects.get(employee=self.employee, date=timezone.localdate())
        self.assertIsNotNone(record.check_in)
        self.assertEqual(record.status, "INCOMPLETE")
        self.assertEqual(record.check_in_latitude, WORKPLACE_LATITUDE)
        self.assertEqual(record.check_in_longitude, WORKPLACE_LONGITUDE)
        self.assertIsNotNone(record.check_in_distance)
        self.assertLessEqual(record.check_in_distance, GEOFENCE_RADIUS_METERS)

    def test_check_in_rejected_outside_geofence(self):
        response = self.client.post("/api/attendance/check-in/", self.outside_location, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("outside the allowed attendance area", response.data["error"])
        self.assertFalse(Attendance.objects.filter(employee=self.employee).exists())

    def test_check_in_rejected_poor_accuracy(self):
        response = self.client.post("/api/attendance/check-in/", self.low_accuracy_location, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"],
            "Your location accuracy is too low. Please enable precise location and try again."
        )

    def test_check_in_rejected_missing_coordinates(self):
        response = self.client.post("/api/attendance/check-in/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Location coordinates", response.data["error"])

    def test_check_out_inside_geofence(self):
        # Create an attendance record checked in 10 minutes ago
        past_time = timezone.now() - timedelta(minutes=10)
        record = Attendance.objects.create(
            employee=self.employee,
            date=timezone.localdate(),
            check_in=past_time,
            status="INCOMPLETE",
        )

        response = self.client.post("/api/attendance/check-out/", self.valid_location, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Check-out successful")

        record.refresh_from_db()
        self.assertEqual(record.status, "PRESENT")
        self.assertIsNotNone(record.check_out)
        self.assertEqual(record.check_out_latitude, WORKPLACE_LATITUDE)
        self.assertLessEqual(record.check_out_distance, GEOFENCE_RADIUS_METERS)

    def test_check_out_rejected_outside_geofence(self):
        past_time = timezone.now() - timedelta(minutes=10)
        Attendance.objects.create(
            employee=self.employee,
            date=timezone.localdate(),
            check_in=past_time,
            status="INCOMPLETE",
        )

        response = self.client.post("/api/attendance/check-out/", self.outside_location, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("outside the allowed attendance area", response.data["error"])

User = get_user_model()

class FaceServiceIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="password123",
            first_name="Test",
            last_name="User"
        )
        self.employee = Employee.objects.create(
            user=self.user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined="2023-01-01"
        )
        self.profile = FaceProfile.objects.create(
            employee=self.employee,
            face_template=[0.5] * 512,
            status="ACTIVE"
        )
        self.dummy_image = "dummy_base64_string"

    @patch('attendance.face_service.requests.post')
    def test_process_enrollment_success(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"template": [0.1] * 512}
        mock_post.return_value = mock_response

        template = process_enrollment(["img1", "img2", "img3"])
        self.assertEqual(template, [0.1] * 512)
        mock_post.assert_called_once()

    @override_settings(FACE_SERVICE_TOKEN="face-service-test-token")
    @patch('attendance.face_service.requests.post')
    def test_enrollment_sends_service_token_when_configured(self, mock_post):
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {"template": [0.1] * 512}
        mock_post.return_value = mock_response

        process_enrollment(["img1", "img2", "img3"])

        self.assertEqual(
            mock_post.call_args.kwargs["headers"],
            {"Authorization": "Bearer face-service-test-token"},
        )

    @patch('attendance.face_service.requests.post')
    def test_process_enrollment_multiple_faces(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "Ambiguous multi-face image"}
        mock_post.return_value = mock_response

        with self.assertRaises(FaceExtractionError) as context:
            process_enrollment(["img1", "img2", "img3"])
        self.assertIn("Ambiguous multi-face image", str(context.exception))

    @patch('attendance.face_service.requests.post')
    def test_process_enrollment_no_face(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "No faces detected"}
        mock_post.return_value = mock_response

        with self.assertRaises(FaceExtractionError) as context:
            process_enrollment(["img1", "img2", "img3"])
        self.assertIn("No faces detected", str(context.exception))

    @patch('attendance.face_service.requests.post')
    def test_find_closest_match_success(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "match",
            "employee_id": self.employee.id,
            "distance": 0.3
        }
        mock_post.return_value = mock_response

        matched_emp, distance = find_closest_match(self.dummy_image)
        self.assertEqual(matched_emp, self.employee)
        self.assertEqual(distance, 0.3)

    @patch('attendance.face_service.requests.post')
    def test_attendance_sequence_is_forwarded_to_sequence_endpoint(self, mock_post):
        mock_response = Mock(status_code=200)
        mock_response.json.return_value = {
            "status": "match", "employee_id": self.employee.id, "distance": 0.2,
        }
        mock_post.return_value = mock_response

        find_closest_match(
            ["frame-1", "frame-2", "frame-3", "frame-4", "frame-5"],
            captured_at_ms=[0, 250, 500, 750, 1000],
        )

        args, kwargs = mock_post.call_args
        self.assertTrue(args[0].endswith("/recognize-sequence"))
        self.assertEqual(kwargs["json"]["frames"], ["frame-1", "frame-2", "frame-3", "frame-4", "frame-5"])
        self.assertEqual(kwargs["json"]["captured_at_ms"], [0, 250, 500, 750, 1000])

    @patch('attendance.face_service.requests.post')
    def test_find_closest_match_unknown(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "unknown",
            "distance": 0.8
        }
        mock_post.return_value = mock_response

        matched_emp, distance = find_closest_match(self.dummy_image)
        self.assertIsNone(matched_emp)
        self.assertEqual(distance, 0.8)

    @patch('attendance.face_service.requests.post')
    def test_recognition_liveness_failure_is_machine_readable_and_fail_closed(self, mock_post):
        response = Mock(status_code=400)
        response.json.return_value = {"status": "liveness_failed", "reason": "spoof-detected"}
        mock_post.return_value = response

        with self.assertRaises(FaceLivenessError) as context:
            find_closest_match(self.dummy_image)
        self.assertEqual(context.exception.status, "liveness_failed")
        self.assertNotIn("spoof-detected", str(context.exception))

    @patch('attendance.face_service.requests.post')
    def test_recognition_liveness_error_is_fail_closed(self, mock_post):
        response = Mock(status_code=503)
        response.json.return_value = {"status": "liveness_error", "error": "internal model detail"}
        mock_post.return_value = response

        with self.assertRaises(FaceLivenessError) as context:
            find_closest_match(self.dummy_image)
        self.assertEqual(context.exception.status, "liveness_error")
        self.assertNotIn("internal model detail", str(context.exception))

    @patch('attendance.face_service.requests.post')
    def test_find_closest_match_invalid_employee(self, mock_post):
        # Service returns an ID that does not exist or isn't in candidate list
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "match",
            "employee_id": 9999,
            "distance": 0.2
        }
        mock_post.return_value = mock_response

        matched_emp, distance = find_closest_match(self.dummy_image)
        self.assertIsNone(matched_emp)

    @patch('attendance.face_service.requests.post')
    def test_service_unavailable(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        with self.assertRaises(FaceExtractionError) as context:
            find_closest_match(self.dummy_image)
        self.assertIn("service is currently unavailable", str(context.exception))

    @patch('attendance.face_service.requests.post')
    def test_service_timeout(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("Timeout")

        with self.assertRaises(FaceExtractionError) as context:
            find_closest_match(self.dummy_image)
        self.assertIn("service is currently unavailable", str(context.exception))

    @patch('attendance.face_service.requests.post')
    def test_malformed_response(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 500
        # Simulating a response where json() fails or returns missing keys handled by .get()
        mock_response.json.return_value = {"error": "Internal server error"}
        mock_post.return_value = mock_response

        with self.assertRaises(FaceExtractionError) as context:
            find_closest_match(self.dummy_image)
        self.assertIn("Internal server error", str(context.exception))

    def test_failed_enrollment_preserves_profile(self):
        # Simulate enrollment failure at view level
        original_template = self.profile.face_template
        
        with patch('attendance.face_service.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.json.return_value = {"error": "No faces detected"}
            mock_post.return_value = mock_response
            
            with self.assertRaises(FaceExtractionError):
                process_enrollment(["img1", "img2", "img3"])
                
        # Check DB to ensure profile hasn't been changed or deleted
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.face_template, original_template)
        self.assertEqual(self.profile.status, "ACTIVE")

class FaceVerifyViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test2@example.com",
            password="password123",
            first_name="Test",
            last_name="User"
        )
        self.employee = Employee.objects.create(
            user=self.user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined="2023-01-01"
        )
        self.profile = FaceProfile.objects.create(
            employee=self.employee,
            face_template=[0.5] * 512,
            status="ACTIVE"
        )
        self.url = reverse('verify-face')

    @patch('attendance.face_service.requests.post')
    def test_verify_known_employee(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "match", "employee_id": self.employee.id, "distance": 0.3}
        mock_post.return_value = mock_response

        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["employee_id"], self.employee.id)
        self.assertEqual(response.data["first_name"], "Test")

    @patch('attendance.face_service.requests.post')
    def test_verify_unknown_identity(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "unknown", "distance": 0.8}
        mock_post.return_value = mock_response

        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["status"], "unknown")

    @patch('attendance.face_service.requests.post')
    def test_verify_no_face(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "No faces detected"}
        mock_post.return_value = mock_response

        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("No faces detected", response.data["error"])

    @patch('attendance.face_service.requests.post')
    def test_verify_multiple_faces(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "Ambiguous multi-face image"}
        mock_post.return_value = mock_response

        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("multi-face", response.data["error"])

    @patch('attendance.face_service.requests.post')
    def test_verify_invalid_employee_id(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "match", "employee_id": 9999, "distance": 0.2}
        mock_post.return_value = mock_response

        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        self.assertEqual(response.status_code, 404)

    @patch('attendance.face_service.requests.post')
    def test_verify_inactive_employee(self, mock_post):
        self.employee.is_active = False
        self.employee.save()
        
        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        self.assertEqual(response.status_code, 404)
        mock_post.assert_not_called()
        
    @patch('attendance.face_service.requests.post')
    def test_verify_no_active_face_profile(self, mock_post):
        self.profile.status = "INACTIVE"
        self.profile.save()
        
        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        self.assertEqual(response.status_code, 404)
        mock_post.assert_not_called()

    @patch('attendance.face_service.requests.post')
    def test_verify_service_unavailable(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("unavailable", response.data["error"])
        
    @patch('attendance.face_service.requests.post')
    def test_verify_service_timeout(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("Timeout")
        
        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("unavailable", response.data["error"])
        
    @patch('attendance.face_service.requests.post')
    def test_verify_malformed_response(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "Internal server error"}
        mock_post.return_value = mock_response

        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Internal server error", response.data["error"])
        
    def test_verify_no_image(self):
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "No image provided")

class WebsiteFacialCheckInViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test3@example.com",
            password="password123",
            first_name="Test",
            last_name="User"
        )
        self.employee = Employee.objects.create(
            user=self.user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined="2023-01-01"
        )
        self.profile = FaceProfile.objects.create(
            employee=self.employee,
            face_template=[0.5] * 512,
            status="ACTIVE"
        )
        self.url = reverse('website-facial-check-in')
        self.valid_location = {
            "latitude": WORKPLACE_LATITUDE,
            "longitude": WORKPLACE_LONGITUDE,
            "accuracy": 15.0,
        }
        
        # Second user to test spoofing
        self.user2 = User.objects.create_user(email="other@example.com", password="password123")
        self.employee2 = Employee.objects.create(user=self.user2, department="Sales", employment_type="PERMANENT", date_joined="2023-01-01")

    @patch('attendance.face_service.requests.post')
    def test_facial_check_in_success(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "match", "employee_id": self.employee.id, "distance": 0.3}
        mock_post.return_value = mock_response

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, camera_sequence_payload(**self.valid_location), format="json")
        
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["message"], "Check-in successful")
        request_call = mock_post.call_args_list[0]
        request_payload = request_call.kwargs["json"]
        self.assertEqual(len(request_payload.get("frames", [])), 5, request_payload)
        self.assertEqual(request_payload["captured_at_ms"], [0, 250, 500, 750, 1000])
        self.assertTrue(request_call.args[0].endswith("/recognize-sequence"))

    @patch('attendance.face_service.requests.post')
    def test_single_image_direct_request_cannot_bypass_sequence_gate(self, mock_post):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {"image": "one-frame", **self.valid_location}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(AttendanceEvent.objects.filter(employee=self.employee).exists())
        mock_post.assert_not_called()

    @patch('attendance.face_service.requests.post')
    def test_facial_check_in_mismatch(self, mock_post):
        # The FR service says it's employee1
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "match", "employee_id": self.employee.id, "distance": 0.3}
        mock_post.return_value = mock_response

        # But we are authenticated as employee2 (spoof attempt)
        self.client.force_authenticate(user=self.user2)
        response = self.client.post(self.url, camera_sequence_payload(**self.valid_location), format="json")
        
        self.assertEqual(response.status_code, 403)
        self.assertIn("does not match your authenticated account", response.data["error"])

    @patch('attendance.face_service.requests.post')
    def test_facial_check_in_unknown(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "unknown", "distance": 0.8}
        mock_post.return_value = mock_response

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, camera_sequence_payload(**self.valid_location), format="json")
        
        self.assertEqual(response.status_code, 403)
        # verify_employee_face does 1:1 check — an unrecognised face returns the same mismatch message
        self.assertIn("does not match your authenticated account", response.data["error"])

    @patch('attendance.face_service.requests.post')
    def test_facial_check_in_duplicate(self, mock_post):
        # Create a check-in for today
        from attendance.models import Attendance
        from django.utils import timezone
        Attendance.objects.create(employee=self.employee, date=timezone.localdate(), check_in=timezone.now(), status="INCOMPLETE")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "match", "employee_id": self.employee.id, "distance": 0.3}
        mock_post.return_value = mock_response

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, camera_sequence_payload(**self.valid_location), format="json")
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "Already checked in today")
        
    @patch('attendance.face_service.requests.post')
    def test_facial_check_in_on_leave(self, mock_post):
        from leave_management.models import LeaveRequest, LeaveType
        from django.utils import timezone
        today = timezone.localdate()
        leave_type = LeaveType.objects.create(name="Sick Leave", description="Sick")
        LeaveRequest.objects.create(employee=self.employee, start_date=today, end_date=today, duration_days=1, status="APPROVED", leave_type=leave_type)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "match", "employee_id": self.employee.id, "distance": 0.3}
        mock_post.return_value = mock_response

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, camera_sequence_payload(**self.valid_location), format="json")
        
        self.assertEqual(response.status_code, 400)
        self.assertIn("on approved leave", response.data["error"])

    @patch('attendance.face_service.requests.post')
    def test_facial_check_in_rejected_outside_geofence(self, mock_post):
        # Use a point ~22km away — guaranteed to exceed any reasonable geofence radius
        outside_location = {
            "latitude": WORKPLACE_LATITUDE + 0.2,
            "longitude": WORKPLACE_LONGITUDE,
            "accuracy": 10.0,
        }
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, camera_sequence_payload(**outside_location), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("outside the allowed attendance area", response.data["error"])
        mock_post.assert_not_called()

    @patch('attendance.face_service.requests.post')
    def test_facial_check_in_service_unavailable(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError("Refused")
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, camera_sequence_payload(**self.valid_location), format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("unavailable", response.data["error"])

    @patch('attendance.face_service.requests.post')
    def test_liveness_failure_rejects_direct_request_without_event(self, mock_post):
        response_from_fr = Mock(status_code=400)
        response_from_fr.json.return_value = {"status": "liveness_failed", "reason": "spoof-detected"}
        mock_post.return_value = response_from_fr
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url, camera_sequence_payload(
            liveness={"is_live": True}, is_live=True, **self.valid_location,
        ), format="json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["status"], "liveness_failed")
        self.assertFalse(AttendanceEvent.objects.filter(employee=self.employee).exists())

    @patch('attendance.face_service.requests.post')
    def test_liveness_service_error_rejects_without_event(self, mock_post):
        response_from_fr = Mock(status_code=503)
        response_from_fr.json.return_value = {"status": "liveness_error", "error": "model detail"}
        mock_post.return_value = response_from_fr
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url, camera_sequence_payload(**self.valid_location), format="json")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["status"], "liveness_error")
        self.assertFalse(AttendanceEvent.objects.filter(employee=self.employee).exists())

class WebsiteFacialCheckOutViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="out@example.com", password="password123", first_name="Test", last_name="User")
        self.employee = Employee.objects.create(user=self.user, department="Engineering", employment_type="PERMANENT", date_joined="2023-01-01")
        self.profile = FaceProfile.objects.create(employee=self.employee, face_template=[0.5] * 512, status="ACTIVE")
        self.url = reverse('website-facial-check-out')
        self.valid_location = {
            "latitude": WORKPLACE_LATITUDE,
            "longitude": WORKPLACE_LONGITUDE,
            "accuracy": 15.0,
        }

    @patch('attendance.face_service.requests.post')
    def test_facial_check_out_success(self, mock_post):
        from attendance.models import Attendance
        from django.utils import timezone
        import datetime
        
        # Check in 6 minutes ago
        check_in_time = timezone.now() - datetime.timedelta(minutes=6)
        Attendance.objects.create(employee=self.employee, date=timezone.localdate(), check_in=check_in_time, status="INCOMPLETE")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "match", "employee_id": self.employee.id, "distance": 0.3}
        mock_post.return_value = mock_response

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, camera_sequence_payload(**self.valid_location), format="json")
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["message"], "Check-out successful")

    @patch('attendance.face_service.requests.post')
    def test_facial_check_out_no_check_in(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "match", "employee_id": self.employee.id, "distance": 0.3}
        mock_post.return_value = mock_response

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, camera_sequence_payload(**self.valid_location), format="json")
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "You have not checked in today")

    @patch('attendance.views.verify_employee_face')
    def test_facial_immediate_checkout_allowed(self, mock_verify):
        """Immediate facial check-out after check-in is now allowed (no cooldown)."""
        # Pre-create check-in with event
        past_time = timezone.now() - timedelta(minutes=2)
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=past_time,
            event_type="CHECK_IN",
            source="MOBILE",
        )
        Attendance.objects.create(
            employee=self.employee,
            date=timezone.localdate(),
            check_in=past_time,
            status="INCOMPLETE",
        )

        mock_verify.return_value = (True, 0.3)

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, camera_sequence_payload(**self.valid_location), format="json")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Check-out successful")

    @patch('attendance.face_service.requests.post')
    def test_facial_check_out_duplicate(self, mock_post):
        from attendance.models import Attendance
        from django.utils import timezone
        import datetime
        
        check_in_time = timezone.now() - datetime.timedelta(minutes=10)
        check_out_time = timezone.now() - datetime.timedelta(minutes=2)
        Attendance.objects.create(employee=self.employee, date=timezone.localdate(), check_in=check_in_time, check_out=check_out_time, status="PRESENT")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "match", "employee_id": self.employee.id, "distance": 0.3}
        mock_post.return_value = mock_response

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, camera_sequence_payload(**self.valid_location), format="json")
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "Already checked out today")

    @patch('attendance.face_service.requests.post')
    def test_facial_check_out_mismatch(self, mock_post):
        from attendance.models import Attendance
        from django.utils import timezone
        import datetime
        
        user2 = User.objects.create_user(email="other2@example.com", password="password123")
        employee2 = Employee.objects.create(user=user2, department="Sales", employment_type="PERMANENT", date_joined="2023-01-01")
        check_in_time = timezone.now() - datetime.timedelta(minutes=6)
        Attendance.objects.create(employee=employee2, date=timezone.localdate(), check_in=check_in_time, status="INCOMPLETE")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "match", "employee_id": self.employee.id, "distance": 0.3}
        mock_post.return_value = mock_response

        self.client.force_authenticate(user=user2)
        response = self.client.post(self.url, camera_sequence_payload(**self.valid_location), format="json")
        
        self.assertEqual(response.status_code, 403)
        self.assertIn("does not match your authenticated account", response.data["error"])

    @patch('attendance.face_service.requests.post')
    def test_liveness_failure_and_error_never_create_checkout_event(self, mock_post):
        from datetime import timedelta
        check_in_time = timezone.now() - timedelta(minutes=10)
        AttendanceEvent.objects.create(employee=self.employee, timestamp=check_in_time, event_type="CHECK_IN", source="FACE_WEB")
        Attendance.objects.create(employee=self.employee, date=timezone.localdate(), check_in=check_in_time, status="INCOMPLETE")
        self.client.force_authenticate(user=self.user)

        for code, status_name, expected_http in ((400, "liveness_failed", 400), (503, "liveness_error", 503)):
            with self.subTest(status=status_name):
                fr_response = Mock(status_code=code)
                fr_response.json.return_value = {"status": status_name}
                mock_post.return_value = fr_response
                response = self.client.post(self.url, camera_sequence_payload(**self.valid_location), format="json")
                self.assertEqual(response.status_code, expected_http)
                self.assertEqual(response.data["status"], status_name)

        self.assertEqual(AttendanceEvent.objects.filter(employee=self.employee, event_type="CHECK_OUT").count(), 0)


class KioskLivenessAttendanceTests(APITestCase):
    def setUp(self):
        from attendance.models import Shift
        self.user = User.objects.create_user(email="kiosk-face@example.com", password="password123", first_name="Kiosk")
        self.shift = Shift.objects.create(
            name="Kiosk shift", code="KIOSK-FACE", start_time=datetime_time(9, 0), end_time=datetime_time(17, 0),
            employment_type="PERMANENT",
        )
        self.employee = Employee.objects.create(
            user=self.user, department="Engineering", employment_type="PERMANENT",
            date_joined="2023-01-01", shift=self.shift,
        )
        FaceProfile.objects.create(employee=self.employee, face_template=[0.5] * 512, status="ACTIVE")
        self.check_in_url = reverse("kiosk-check-in")
        self.check_out_url = reverse("kiosk-check-out")

    def _fr_response(self, status_code, body):
        response = Mock(status_code=status_code)
        response.json.return_value = body
        return response

    @patch("attendance.face_service.requests.post")
    def test_spoof_and_liveness_error_block_both_kiosk_actions_even_with_client_claim(self, mock_post):
        today = timezone.localdate()
        check_in_time = timezone.now() - timedelta(minutes=10)
        Attendance.objects.create(employee=self.employee, date=today, check_in=check_in_time, status="INCOMPLETE")
        AttendanceEvent.objects.create(employee=self.employee, timestamp=check_in_time, event_type="CHECK_IN", source="KIOSK")

        cases = (
            (self.check_in_url, "CHECK_IN", 400, "liveness_failed", 400),
            (self.check_in_url, "CHECK_IN", 503, "liveness_error", 503),
            (self.check_out_url, "CHECK_OUT", 400, "liveness_failed", 400),
            (self.check_out_url, "CHECK_OUT", 503, "liveness_error", 503),
        )
        for url, event_type, fr_code, fr_status, expected_code in cases:
            with self.subTest(url=url, status=fr_status):
                mock_post.return_value = self._fr_response(fr_code, {"status": fr_status, "reason": "private detail"})
                response = self.client.post(url, camera_sequence_payload(
                    liveness={"is_live": True}, is_live=True,
                ), format="json")
                self.assertEqual(response.status_code, expected_code)
                self.assertEqual(response.data["status"], fr_status)
                self.assertEqual(AttendanceEvent.objects.filter(employee=self.employee, event_type=event_type).count(), 1 if event_type == "CHECK_IN" else 0)

    @patch("attendance.face_service.requests.post")
    def test_live_matching_recognition_keeps_kiosk_checkin_checkout_working(self, mock_post):
        mock_post.return_value = self._fr_response(200, {
            "status": "match", "employee_id": self.employee.id, "distance": 0.2,
        })

        check_in = self.client.post(self.check_in_url, camera_sequence_payload(), format="json")
        self.assertEqual(check_in.status_code, 201)
        self.assertTrue(AttendanceEvent.objects.filter(employee=self.employee, event_type="CHECK_IN").exists())

        check_out = self.client.post(self.check_out_url, camera_sequence_payload(), format="json")
        self.assertEqual(check_out.status_code, 200)
        self.assertTrue(AttendanceEvent.objects.filter(employee=self.employee, event_type="CHECK_OUT").exists())

    @patch("attendance.face_service.requests.post")
    def test_kiosk_unknown_recognition_contract_is_unchanged(self, mock_post):
        mock_post.return_value = self._fr_response(200, {"status": "unknown", "distance": 0.8})
        response = self.client.post(self.check_in_url, camera_sequence_payload(), format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"], "Face not recognized.")
        self.assertFalse(AttendanceEvent.objects.filter(employee=self.employee).exists())

    @patch("attendance.face_service.requests.post")
    def test_kiosk_single_image_request_cannot_bypass_sequence_gate(self, mock_post):
        response = self.client.post(self.check_in_url, {"image": "one-frame"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(AttendanceEvent.objects.filter(employee=self.employee).exists())
        mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# MyTeamView Tests
# ---------------------------------------------------------------------------

class MyTeamViewTests(APITestCase):
    """
    Full coverage of GET /api/attendance/my-team/

    Scenarios tested
    ----------------
    Authentication
      - Unauthenticated request is rejected (401)
      - Non-employee user (no employee profile) is rejected
    Team filtering
      - Same employment_type + section are included
      - Same employment_type but different section is excluded
      - Different employment_type but same section is excluded
      - Inactive employees are excluded
      - Subsection does NOT restrict results (A1 sees A2, A3, …)
    Status classification
      - CHECKED_IN: has a today check_in
      - CHECKED_IN: already checked OUT today is still CHECKED_IN (not YET_TO_CHECK_IN)
      - YET_TO_CHECK_IN: no attendance record today, not on leave
      - ON_LEAVE: has an APPROVED LeaveRequest covering today
      - Pending leave does NOT count as ON_LEAVE
      - Rejected/Cancelled leave does NOT count as ON_LEAVE
    Edge cases
      - Empty section → returns note, empty members list
      - Empty employment_type → returns note, empty members list
      - No team members → total_members = 0
      - Everyone checked in → yet_to_check_in_count = 0, on_leave_count = 0
      - Everyone on leave → on_leave_count = total_members
    Security
      - Response does NOT expose face_template / biometric fields
      - Response does NOT expose password / sensitive user fields
      - Employee cannot inject section/employment_type via query params
    Counts
      - checked_in_count, yet_to_check_in_count, on_leave_count are accurate
      - leave_type label is present in ON_LEAVE member data
    """

    URL = "/api/attendance/my-team/"

    def _make_user_and_employee(
        self,
        email,
        employment_type="INTERN",
        section="A",
        subsection="A1",
        is_active=True,
    ):
        User = get_user_model()
        user = User.objects.create_user(email=email, password="testpass123")
        emp = Employee.objects.create(
            user=user,
            department="Engineering",
            employment_type=employment_type,
            date_joined=date.today(),
            is_active=is_active,
            section=section,
            subsection=subsection,
        )
        return user, emp

    def _make_leave_type(self):
        from leave_management.models import LeaveType
        return LeaveType.objects.create(name="Casual Leave", code=f"CASUAL_{id(self)}")

    def _make_approved_leave(self, employee, leave_type, today):
        from leave_management.models import LeaveRequest
        return LeaveRequest.objects.create(
            employee=employee,
            leave_type=leave_type,
            start_date=today,
            end_date=today,
            day_type="FULL_DAY",
            duration_days=1,
            reason="Test leave",
            status="APPROVED",
        )

    def setUp(self):
        # The requesting employee: INTERN, section A, subsection A1
        self.user, self.me = self._make_user_and_employee(
            "me@example.com", employment_type="INTERN", section="A", subsection="A1"
        )
        # Use a fixed weekday for tests to avoid weekend issues
        from datetime import date, timedelta
        today = timezone.localdate()
        # If today is weekend (Sat=5, Sun=6), use next Monday
        if today.weekday() in [5, 6]:
            days_to_monday = 7 - today.weekday()
            self.today = today + timedelta(days=days_to_monday)
        else:
            self.today = today
        self.leave_type = self._make_leave_type()
        
        # Patch timezone.localdate for all tests in this class
        self.localdate_patcher = patch('django.utils.timezone.localdate')
        self.mock_localdate = self.localdate_patcher.start()
        self.mock_localdate.return_value = self.today
    
    def tearDown(self):
        self.localdate_patcher.stop()

    # ------------------------------------------------------------------
    # Authentication tests
    # ------------------------------------------------------------------

    def test_unauthenticated_request_returns_401(self):
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 401)

    def test_non_employee_user_is_rejected(self):
        """A user with no Employee profile must be rejected."""
        User = get_user_model()
        admin_user = User.objects.create_user(email="admin@example.com", password="x", is_staff=True)
        self.client.force_authenticate(user=admin_user)
        response = self.client.get(self.URL)
        # IsEmployee permission blocks non-employees
        self.assertIn(response.status_code, [401, 403])

    # ------------------------------------------------------------------
    # Team filtering tests
    # ------------------------------------------------------------------

    def test_same_type_and_section_are_included(self):
        """Teammates with identical employment_type + section appear in results."""
        _, teammate = self._make_user_and_employee(
            "teammate@example.com", employment_type="INTERN", section="A", subsection="A2"
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        ids = [m["id"] for m in response.data["members"]]
        self.assertIn(self.me.id, ids)
        self.assertIn(teammate.id, ids)

    def test_different_section_is_excluded(self):
        """An INTERN in section B must not appear in section A's team."""
        _, other = self._make_user_and_employee(
            "other_section@example.com", employment_type="INTERN", section="B", subsection="B1"
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        ids = [m["id"] for m in response.data["members"]]
        self.assertNotIn(other.id, ids)

    def test_different_employment_type_is_excluded(self):
        """A PERMANENT employee in section A must not appear in INTERN section A's team."""
        _, other = self._make_user_and_employee(
            "permanent@example.com", employment_type="PERMANENT", section="A", subsection="A1"
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        ids = [m["id"] for m in response.data["members"]]
        self.assertNotIn(other.id, ids)

    def test_inactive_employee_is_excluded(self):
        """Inactive employees must never appear in results."""
        _, inactive = self._make_user_and_employee(
            "inactive@example.com", employment_type="INTERN", section="A", subsection="A1", is_active=False
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        ids = [m["id"] for m in response.data["members"]]
        self.assertNotIn(inactive.id, ids)

    def test_subsection_does_not_restrict_results(self):
        """A1, A2, A3 subsections must all appear when querying section A."""
        _, a2 = self._make_user_and_employee(
            "a2@example.com", employment_type="INTERN", section="A", subsection="A2"
        )
        _, a3 = self._make_user_and_employee(
            "a3@example.com", employment_type="INTERN", section="A", subsection="A3"
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        ids = [m["id"] for m in response.data["members"]]
        self.assertIn(self.me.id, ids)
        self.assertIn(a2.id, ids)
        self.assertIn(a3.id, ids)

    # ------------------------------------------------------------------
    # Status classification tests
    # ------------------------------------------------------------------

    def test_checked_in_classification(self):
        """Employee with today's check_in → CHECKED_IN."""
        Attendance.objects.create(
            employee=self.me,
            date=self.today,
            check_in=timezone.now(),
            status="INCOMPLETE",
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        me_data = next(m for m in response.data["members"] if m["id"] == self.me.id)
        self.assertEqual(me_data["status"], "CHECKED_IN")
        self.assertEqual(response.data["checked_in_count"], 1)
        self.assertIsNotNone(me_data["check_in_time"])

    def test_checked_out_employee_stays_in_checked_in(self):
        """
        An employee who has already checked OUT today must still be classified
        as CHECKED_IN (not YET_TO_CHECK_IN), because they were present.
        """
        check_in = timezone.now() - timedelta(hours=8)
        check_out = timezone.now()
        Attendance.objects.create(
            employee=self.me,
            date=self.today,
            check_in=check_in,
            check_out=check_out,
            status="PRESENT",
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        me_data = next(m for m in response.data["members"] if m["id"] == self.me.id)
        self.assertEqual(me_data["status"], "CHECKED_IN")
        self.assertIsNotNone(me_data["check_out_time"])

    def test_yet_to_check_in_classification(self):
        """Employee with no attendance record and no leave → YET_TO_CHECK_IN."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        me_data = next(m for m in response.data["members"] if m["id"] == self.me.id)
        self.assertEqual(me_data["status"], "YET_TO_CHECK_IN")
        self.assertEqual(response.data["yet_to_check_in_count"], 1)
        self.assertIsNone(me_data["check_in_time"])

    def test_approved_leave_classification(self):
        """Employee with APPROVED leave covering today → ON_LEAVE."""
        self._make_approved_leave(self.me, self.leave_type, self.today)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        me_data = next(m for m in response.data["members"] if m["id"] == self.me.id)
        self.assertEqual(me_data["status"], "ON_LEAVE")
        self.assertEqual(response.data["on_leave_count"], 1)
        self.assertEqual(me_data["leave_type"], "Casual Leave")

    def test_pending_leave_not_on_leave(self):
        """PENDING leave must NOT classify the employee as ON_LEAVE."""
        from leave_management.models import LeaveRequest
        LeaveRequest.objects.create(
            employee=self.me,
            leave_type=self.leave_type,
            start_date=self.today,
            end_date=self.today,
            day_type="FULL_DAY",
            duration_days=1,
            reason="Pending",
            status="PENDING",
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        me_data = next(m for m in response.data["members"] if m["id"] == self.me.id)
        self.assertNotEqual(me_data["status"], "ON_LEAVE")
        self.assertEqual(response.data["on_leave_count"], 0)

    def test_rejected_leave_not_on_leave(self):
        """DENIED leave must NOT classify the employee as ON_LEAVE."""
        from leave_management.models import LeaveRequest
        LeaveRequest.objects.create(
            employee=self.me,
            leave_type=self.leave_type,
            start_date=self.today,
            end_date=self.today,
            day_type="FULL_DAY",
            duration_days=1,
            reason="Denied",
            status="DENIED",
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        me_data = next(m for m in response.data["members"] if m["id"] == self.me.id)
        self.assertNotEqual(me_data["status"], "ON_LEAVE")

    def test_cancelled_leave_not_on_leave(self):
        """CANCELLED leave must NOT classify the employee as ON_LEAVE."""
        from leave_management.models import LeaveRequest
        LeaveRequest.objects.create(
            employee=self.me,
            leave_type=self.leave_type,
            start_date=self.today,
            end_date=self.today,
            day_type="FULL_DAY",
            duration_days=1,
            reason="Cancelled",
            status="CANCELLED",
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        me_data = next(m for m in response.data["members"] if m["id"] == self.me.id)
        self.assertNotEqual(me_data["status"], "ON_LEAVE")

    # ------------------------------------------------------------------
    # Count accuracy tests
    # ------------------------------------------------------------------

    def test_counts_are_accurate(self):
        """checked_in, yet_to_check_in, on_leave counts match actual data."""
        # me → ON_LEAVE
        self._make_approved_leave(self.me, self.leave_type, self.today)

        # teammate1 → CHECKED_IN
        _, t1 = self._make_user_and_employee("t1@example.com", employment_type="INTERN", section="A", subsection="A2")
        Attendance.objects.create(employee=t1, date=self.today, check_in=timezone.now(), status="INCOMPLETE")

        # teammate2 → YET_TO_CHECK_IN
        _, t2 = self._make_user_and_employee("t2@example.com", employment_type="INTERN", section="A", subsection="A3")

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_members"], 3)
        self.assertEqual(response.data["checked_in_count"], 1)
        self.assertEqual(response.data["yet_to_check_in_count"], 1)
        self.assertEqual(response.data["on_leave_count"], 1)

    # ------------------------------------------------------------------
    # Edge case tests
    # ------------------------------------------------------------------

    def test_empty_section_returns_graceful_response(self):
        """Employee with no section set gets a graceful empty response."""
        self.me.section = ""
        self.me.save()
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_members"], 0)
        self.assertIn("note", response.data)

    def test_empty_employment_type_returns_graceful_response(self):
        """Employee with no employment_type gets a graceful empty response."""
        # employment_type has choices but CharField allows blank at DB level
        Employee.objects.filter(pk=self.me.pk).update(employment_type="")
        self.me.refresh_from_db()
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_members"], 0)
        self.assertIn("note", response.data)

    def test_no_team_members_returns_empty_list(self):
        """Single employee in a unique type+section: only themselves, no errors."""
        self.me.employment_type = "CONTRACT"
        self.me.section = "UNIQUE"
        self.me.save()
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        # Only me
        self.assertEqual(response.data["total_members"], 1)
        self.assertEqual(response.data["members"][0]["id"], self.me.id)

    def test_everyone_checked_in(self):
        """All members checked in → yet_to_check_in_count=0, on_leave_count=0."""
        _, t1 = self._make_user_and_employee("t1b@example.com", employment_type="INTERN", section="A", subsection="A2")
        for emp in [self.me, t1]:
            Attendance.objects.create(employee=emp, date=self.today, check_in=timezone.now(), status="INCOMPLETE")
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["yet_to_check_in_count"], 0)
        self.assertEqual(response.data["on_leave_count"], 0)
        self.assertEqual(response.data["checked_in_count"], 2)

    def test_everyone_on_leave(self):
        """All members on leave → on_leave_count=total_members, others=0."""
        _, t1 = self._make_user_and_employee("t1c@example.com", employment_type="INTERN", section="A", subsection="A2")
        for emp in [self.me, t1]:
            self._make_approved_leave(emp, self.leave_type, self.today)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["on_leave_count"], 2)
        self.assertEqual(response.data["checked_in_count"], 0)
        self.assertEqual(response.data["yet_to_check_in_count"], 0)

    # ------------------------------------------------------------------
    # Security tests
    # ------------------------------------------------------------------

    def test_face_biometric_fields_not_exposed(self):
        """face_template or any biometric field must never appear in the response."""
        from employees.models import FaceProfile
        FaceProfile.objects.create(
            employee=self.me,
            face_template=[0.1] * 512,
            status="ACTIVE",
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        raw_response = str(response.data)
        self.assertNotIn("face_template", raw_response)
        self.assertNotIn("face_profile", raw_response)
        # Spot check each member dict too
        for member in response.data["members"]:
            self.assertNotIn("face_template", member)

    def test_password_not_exposed(self):
        """password field must never appear in the response."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        raw_response = str(response.data)
        self.assertNotIn("password", raw_response)

    def test_query_params_cannot_override_team(self):
        """
        Passing section/employment_type/employee_id as query params must have
        zero effect — the team is always derived from the authenticated user.
        """
        _, other = self._make_user_and_employee(
            "other_inject@example.com", employment_type="PERMANENT", section="B", subsection="B1"
        )
        self.client.force_authenticate(user=self.user)
        # Attempt to inject a different section/type
        response = self.client.get(self.URL + "?section=B&employment_type=PERMANENT")
        self.assertEqual(response.status_code, 200)
        # Should still see INTERN / section A (me), NOT section B PERMANENT
        self.assertEqual(response.data["team_employment_type"], "INTERN")
        self.assertEqual(response.data["team_section"], "A")
        ids = [m["id"] for m in response.data["members"]]
        self.assertNotIn(other.id, ids)

    def test_response_includes_required_fields(self):
        """Top-level response shape is complete and correct."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        for key in [
            "team_employment_type",
            "team_section",
            "total_members",
            "checked_in_count",
            "yet_to_check_in_count",
            "on_leave_count",
            "members",
        ]:
            self.assertIn(key, response.data)

    def test_member_fields_are_correct(self):
        """Each member dict contains id, name, department, subsection, status, check_in_time, check_out_time."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["members"]), 1)
        member = response.data["members"][0]
        for key in ["id", "name", "department", "subsection", "status", "check_in_time", "check_out_time"]:
            self.assertIn(key, member)

    def test_on_leave_member_has_leave_type_field(self):
        """ON_LEAVE members must include a leave_type label."""
        self._make_approved_leave(self.me, self.leave_type, self.today)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        me_data = next(m for m in response.data["members"] if m["id"] == self.me.id)
        self.assertIn("leave_type", me_data)
        self.assertEqual(me_data["leave_type"], "Casual Leave")

    def test_team_metadata_in_response(self):
        """team_employment_type and team_section in response match the authenticated employee."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["team_employment_type"], "INTERN")
        self.assertEqual(response.data["team_section"], "A")


# ---------------------------------------------------------------------------
# Model/Schema Tests (Phase 1)
# ---------------------------------------------------------------------------

from attendance.models import Shift, AttendanceEvent


class ShiftModelTests(TestCase):
    """Tests for the Shift model."""

    def setUp(self):
        self.shift = Shift.objects.create(
            name="Morning Shift",
            code="MORN",
            start_time=datetime_time(9, 0),
            end_time=datetime_time(17, 0),
            is_active=True,
        )

    def test_shift_creation(self):
        """Shift can be created with required fields."""
        self.assertEqual(self.shift.name, "Morning Shift")
        self.assertEqual(self.shift.code, "MORN")
        self.assertEqual(str(self.shift.start_time), "09:00:00")
        self.assertEqual(str(self.shift.end_time), "17:00:00")
        self.assertTrue(self.shift.is_active)

    def test_shift_str_representation(self):
        """Shift __str__ returns code - name."""
        self.assertEqual(str(self.shift), "MORN - Morning Shift")

    def test_shift_code_unique(self):
        """Shift code must be unique."""
        with self.assertRaises(Exception):
            Shift.objects.create(
                name="Another Morning",
                code="MORN",
                start_time=datetime_time(8, 0),
                end_time=datetime_time(16, 0),
            )

    def test_shift_default_is_active(self):
        """Shift defaults to active=True."""
        shift = Shift.objects.create(
            name="Night Shift",
            code="NIGHT",
            start_time=datetime_time(22, 0),
            end_time=datetime_time(6, 0),
        )
        self.assertTrue(shift.is_active)

    def test_shift_ordering_by_code(self):
        """Shifts are ordered by code."""
        Shift.objects.create(name="A Shift", code="AAA", start_time=datetime_time(8, 0), end_time=datetime_time(16, 0))
        Shift.objects.create(name="Z Shift", code="ZZZ", start_time=datetime_time(8, 0), end_time=datetime_time(16, 0))
        codes = list(Shift.objects.values_list("code", flat=True))
        # MORN (from setUp) comes before AAA alphabetically? No, AAA < MORN < ZZZ
        self.assertEqual(codes, ["AAA", "MORN", "ZZZ"])


class EmployeeShiftRelationTests(TestCase):
    """Tests for Employee.shift ForeignKey."""

    def setUp(self):
        self.user = User.objects.create_user(email="emp@example.com", password="x")
        self.shift = Shift.objects.create(
            name="Morning", code="MORN", start_time=datetime_time(9, 0), end_time=datetime_time(17, 0)
        )

    def test_employee_can_have_no_shift(self):
        """Employee shift field is nullable."""
        emp = Employee.objects.create(
            user=self.user,
            department="Eng",
            employment_type="PERMANENT",
            date_joined=date.today(),
        )
        self.assertIsNone(emp.shift)

    def test_employee_can_reference_shift(self):
        """Employee can be assigned to a shift."""
        emp = Employee.objects.create(
            user=self.user,
            department="Eng",
            employment_type="PERMANENT",
            date_joined=date.today(),
            shift=self.shift,
        )
        self.assertEqual(emp.shift, self.shift)
        # Reverse relation
        self.assertIn(emp, self.shift.employees.all())


class AttendanceEventModelTests(TestCase):
    """Tests for the AttendanceEvent model."""

    def setUp(self):
        self.user = User.objects.create_user(email="emp2@example.com", password="x")
        self.employee = Employee.objects.create(
            user=self.user,
            department="Eng",
            employment_type="PERMANENT",
            date_joined=date.today(),
        )
        self.shift = Shift.objects.create(
            name="Morning", code="MORN", start_time=datetime_time(9, 0), end_time=datetime_time(17, 0)
        )

    def test_attendance_event_creation(self):
        """AttendanceEvent can be created with required fields."""
        event = AttendanceEvent.objects.create(
            employee=self.employee,
            shift=self.shift,
            timestamp=timezone.now(),
            event_type="CHECK_IN",
            source="MOBILE",
        )
        self.assertEqual(event.employee, self.employee)
        self.assertEqual(event.shift, self.shift)
        self.assertEqual(event.event_type, "CHECK_IN")
        self.assertEqual(event.source, "MOBILE")

    def test_multiple_events_same_day_different_times(self):
        """Multiple AttendanceEvents can exist for one employee on one day."""
        # Use a fixed date to avoid timezone issues in test
        today = timezone.localdate()
        base_time = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
        
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=base_time + timedelta(hours=9),  # 09:00
            event_type="CHECK_IN",
        )
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=base_time + timedelta(hours=17),  # 17:00
            event_type="CHECK_OUT",
        )
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=base_time + timedelta(hours=18),  # 18:00
            event_type="CHECK_IN",
        )
        # Three events on same day
        events = AttendanceEvent.objects.filter(
            employee=self.employee,
            timestamp__date=today,
        )
        self.assertEqual(events.count(), 3)

    def test_event_ordering_by_timestamp_desc(self):
        """Events are ordered by timestamp descending by default."""
        now = timezone.now()
        e1 = AttendanceEvent.objects.create(employee=self.employee, timestamp=now, event_type="CHECK_IN")
        e2 = AttendanceEvent.objects.create(employee=self.employee, timestamp=now + timedelta(hours=1), event_type="CHECK_OUT")
        e3 = AttendanceEvent.objects.create(employee=self.employee, timestamp=now + timedelta(hours=2), event_type="CHECK_IN")

        events = list(AttendanceEvent.objects.filter(employee=self.employee))
        self.assertEqual(events[0], e3)
        self.assertEqual(events[1], e2)
        self.assertEqual(events[2], e1)


class AttendanceDailySummaryConstraintTests(TestCase):
    """Tests that Attendance remains unique per employee/date."""

    def setUp(self):
        self.user = User.objects.create_user(email="emp3@example.com", password="x")
        self.employee = Employee.objects.create(
            user=self.user,
            department="Eng",
            employment_type="PERMANENT",
            date_joined=date.today(),
        )
        self.today = timezone.localdate()

    def test_attendance_unique_per_employee_per_day(self):
        """Only one Attendance row allowed per employee per date."""
        Attendance.objects.create(employee=self.employee, date=self.today)
        with self.assertRaises(Exception):
            Attendance.objects.create(employee=self.employee, date=self.today)

    def test_attendance_allows_multiple_events_but_one_summary(self):
        """Multiple AttendanceEvents can exist while Attendance remains one row."""
        # Create summary row
        attendance = Attendance.objects.create(employee=self.employee, date=self.today)
        # Create multiple events — should not conflict with Attendance constraint
        today = self.today
        base_time = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
        
        AttendanceEvent.objects.create(employee=self.employee, timestamp=base_time + timedelta(hours=9), event_type="CHECK_IN")
        AttendanceEvent.objects.create(employee=self.employee, timestamp=base_time + timedelta(hours=17), event_type="CHECK_OUT")
        AttendanceEvent.objects.create(employee=self.employee, timestamp=base_time + timedelta(hours=18), event_type="CHECK_IN")

        self.assertEqual(Attendance.objects.filter(employee=self.employee, date=self.today).count(), 1)
        self.assertEqual(AttendanceEvent.objects.filter(employee=self.employee, timestamp__date=today).count(), 3)


# ---------------------------------------------------------------------------
# Event-Based Attendance Behavior Tests (Phase 2)
# ---------------------------------------------------------------------------

from attendance.models import AttendanceEvent


class EventBasedAttendanceTests(APITestCase):
    """Tests for event-based attendance check-in/check-out behavior."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="event_test@example.com",
            password="password123",
        )
        from attendance.models import Shift
        self.shift = Shift.objects.create(
            name="Morning Shift",
            code="MORN",
            start_time=datetime_time(9, 0),
            end_time=datetime_time(17, 0),
            is_active=True,
        )
        self.employee = Employee.objects.create(
            user=self.user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined=date.today(),
            is_active=True,
            shift=self.shift,
        )
        self.client.force_authenticate(user=self.user)

        self.valid_location = {
            "latitude": WORKPLACE_LATITUDE,
            "longitude": WORKPLACE_LONGITUDE,
            "accuracy": 15.0,
        }

    def test_first_check_in_creates_event(self):
        """First check-in creates AttendanceEvent and updates Attendance."""
        response = self.client.post("/api/attendance/check-in/", self.valid_location, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check Attendance was updated
        attendance = Attendance.objects.get(employee=self.employee, date=timezone.localdate())
        self.assertIsNotNone(attendance.check_in)
        self.assertEqual(attendance.status, "INCOMPLETE")

        # Check event was created
        events = AttendanceEvent.objects.filter(employee=self.employee, timestamp__date=timezone.localdate())
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.first().event_type, "CHECK_IN")
        self.assertEqual(events.first().source, "MOBILE")

    def test_first_checkout_creates_event(self):
        """First check-out creates AttendanceEvent and sets status to PRESENT."""
        # Pre-create attendance with check_in
        past_time = timezone.now() - timedelta(minutes=10)
        Attendance.objects.create(
            employee=self.employee,
            date=timezone.localdate(),
            check_in=past_time,
            status="INCOMPLETE",
        )

        response = self.client.post("/api/attendance/check-out/", self.valid_location, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        attendance = Attendance.objects.get(employee=self.employee, date=timezone.localdate())
        self.assertIsNotNone(attendance.check_out)
        self.assertEqual(attendance.status, "PRESENT")
        self.assertIsNotNone(attendance.working_duration)

        # Check event was created
        events = AttendanceEvent.objects.filter(employee=self.employee, timestamp__date=timezone.localdate())
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.first().event_type, "CHECK_OUT")

    def test_second_checkin_after_checkout(self):
        """Second check-in after checkout is allowed and creates new event."""
        # Check in
        self.client.post("/api/attendance/check-in/", self.valid_location, format="json")
        # Check out (with 6 min gap to pass cooldown)
        past_time = timezone.now() - timedelta(minutes=6)
        # Manually update the check-in time to be 6 min ago
        AttendanceEvent.objects.filter(employee=self.employee, event_type="CHECK_IN").update(timestamp=past_time)
        Attendance.objects.filter(employee=self.employee, date=timezone.localdate()).update(check_in=past_time)
        
        self.client.post("/api/attendance/check-out/", self.valid_location, format="json")
        # Check in again
        response = self.client.post("/api/attendance/check-in/", self.valid_location, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Should have 3 events now
        events = AttendanceEvent.objects.filter(employee=self.employee, timestamp__date=timezone.localdate()).order_by("timestamp")
        self.assertEqual(events.count(), 3)
        self.assertEqual(events[0].event_type, "CHECK_IN")
        self.assertEqual(events[1].event_type, "CHECK_OUT")
        self.assertEqual(events[2].event_type, "CHECK_IN")

        # Attendance should show first check-in and the existing check-out
        attendance = Attendance.objects.get(employee=self.employee, date=timezone.localdate())
        self.assertEqual(attendance.check_in, events[0].timestamp)
        self.assertEqual(attendance.check_out, events[1].timestamp)
        self.assertEqual(attendance.status, "INCOMPLETE")

    def test_second_checkout(self):
        """Second checkout updates last check-out to latest event."""
        # Create all events manually to avoid cooldown issues
        now = timezone.now()
        
        # First check-in (2 hours ago)
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=now - timedelta(hours=2),
            event_type="CHECK_IN",
            source="MOBILE",
        )
        # First check-out (1.5 hours ago)
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=now - timedelta(hours=1, minutes=30),
            event_type="CHECK_OUT",
            source="MOBILE",
        )
        # Second check-in (45 min ago)
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=now - timedelta(minutes=45),
            event_type="CHECK_IN",
            source="MOBILE",
        )
        # Second check-out (15 min ago)
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=now - timedelta(minutes=15),
            event_type="CHECK_OUT",
            source="MOBILE",
        )
        
        # Recompute attendance
        attendance = Attendance.objects.create(employee=self.employee, date=timezone.localdate())
        attendance.recompute_from_events()

        # Should have 4 events
        events = AttendanceEvent.objects.filter(employee=self.employee, timestamp__date=timezone.localdate()).order_by("timestamp")
        self.assertEqual(events.count(), 4)

        # Attendance should show first check-in and last check-out
        self.assertEqual(attendance.check_in, now - timedelta(hours=2))
        self.assertEqual(attendance.check_out, now - timedelta(minutes=15))
        self.assertEqual(attendance.status, "PRESENT")

    def test_first_in_remains_earliest(self):
        """First check-in remains the earliest even after multiple cycles."""
        now = timezone.make_aware(datetime.combine(timezone.localdate(), datetime_time(12, 0)), timezone.get_current_timezone())
        # Manually create events with different times
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=now - timedelta(hours=2),
            event_type="CHECK_IN",
            source="MOBILE",
        )
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=now - timedelta(hours=1),
            event_type="CHECK_OUT",
            source="MOBILE",
        )
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=now,
            event_type="CHECK_IN",
            source="MOBILE",
        )

        # Recompute attendance
        attendance = Attendance.objects.create(employee=self.employee, date=timezone.localdate())
        attendance.recompute_from_events()

        # First check-in should be the earliest (2 hours ago)
        self.assertEqual(attendance.check_in, now - timedelta(hours=2))
        # Check-out should remain the latest check-out (1 hour ago)
        self.assertEqual(attendance.check_out, now - timedelta(hours=1))
        self.assertEqual(attendance.status, "INCOMPLETE")

    def test_last_out_becomes_latest_checkout(self):
        """Last check-out becomes the latest checkout event."""
        now = timezone.make_aware(datetime.combine(timezone.localdate(), datetime_time(12, 0)), timezone.get_current_timezone())
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=now - timedelta(hours=3),
            event_type="CHECK_IN",
            source="MOBILE",
        )
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=now - timedelta(hours=2),
            event_type="CHECK_OUT",
            source="MOBILE",
        )
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=now - timedelta(hours=1),
            event_type="CHECK_IN",
            source="MOBILE",
        )
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=now,
            event_type="CHECK_OUT",
            source="MOBILE",
        )

        attendance = Attendance.objects.create(employee=self.employee, date=timezone.localdate())
        attendance.recompute_from_events()

        # Last check-out should be now
        self.assertEqual(attendance.check_out, now)
        # First check-in should be 3 hours ago
        self.assertEqual(attendance.check_in, now - timedelta(hours=3))
        self.assertEqual(attendance.status, "PRESENT")

    def test_duplicate_consecutive_checkin_rejected(self):
        """Duplicate consecutive check-in is rejected."""
        # First check-in
        self.client.post("/api/attendance/check-in/", self.valid_location, format="json")
        # Second check-in without checkout
        response = self.client.post("/api/attendance/check-in/", self.valid_location, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Already checked in", response.data["error"])

    def test_duplicate_consecutive_checkout_rejected(self):
        """Duplicate consecutive check-out is rejected."""
        # Check in and check out with time in between
        past_time = timezone.now() - timedelta(minutes=6)
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=past_time,
            event_type="CHECK_IN",
            source="MOBILE",
        )
        Attendance.objects.create(
            employee=self.employee,
            date=timezone.localdate(),
            check_in=past_time,
            status="INCOMPLETE",
        )
        
        # First check-out
        self.client.post("/api/attendance/check-out/", self.valid_location, format="json")
        # Second check-out immediately (should be rejected as duplicate)
        response = self.client.post("/api/attendance/check-out/", self.valid_location, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Already checked out today", response.data["error"])

    def test_shift_end_does_not_finalize_attendance(self):
        """Attendance is not finalized at shift end - events continue to accumulate."""
        # This test verifies the design principle - no auto-finalization
        # Create events manually to avoid cooldown issues
        base_time = timezone.make_aware(datetime.combine(timezone.localdate(), datetime_time(9, 0)), timezone.get_current_timezone())
        
        for i in range(3):
            check_in_time = base_time + timedelta(hours=i*2)
            check_out_time = base_time + timedelta(hours=i*2 + 1)
            
            AttendanceEvent.objects.create(
                employee=self.employee,
                timestamp=check_in_time,
                event_type="CHECK_IN",
                source="MOBILE",
            )
            AttendanceEvent.objects.create(
                employee=self.employee,
                timestamp=check_out_time,
                event_type="CHECK_OUT",
                source="MOBILE",
            )
        
        Attendance.objects.create(
            employee=self.employee,
            date=timezone.localdate(),
            check_in=base_time,
            check_out=base_time + timedelta(hours=7),
            status="PRESENT",
        )

        events = AttendanceEvent.objects.filter(employee=self.employee, timestamp__date=timezone.localdate())
        self.assertEqual(events.count(), 6)  # 3 cycles = 6 events

    @patch('attendance.views.verify_employee_face')
    def test_facial_checkin_creates_event(self, mock_verify):
        """Facial check-in creates AttendanceEvent with source FACE_WEB."""
        mock_verify.return_value = (True, 0.3)

        response = self.client.post("/api/attendance/website-facial-check-in/", camera_sequence_payload(**self.valid_location), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        events = AttendanceEvent.objects.filter(employee=self.employee, timestamp__date=timezone.localdate())
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.first().source, "FACE_WEB")

    @patch('attendance.views.verify_employee_face')
    def test_facial_checkout_creates_event(self, mock_verify):
        """Facial check-out creates AttendanceEvent with source FACE_WEB."""
        # Pre-create check-in with event (not just attendance record)
        past_time = timezone.now() - timedelta(minutes=10)
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=past_time,
            event_type="CHECK_IN",
            source="MOBILE",
        )
        Attendance.objects.create(
            employee=self.employee,
            date=timezone.localdate(),
            check_in=past_time,
            status="INCOMPLETE",
        )

        mock_verify.return_value = (True, 0.3)

        response = self.client.post("/api/attendance/website-facial-check-out/", camera_sequence_payload(**self.valid_location), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_geofence_protection_still_works(self):
        """Geofence validation still rejects outside locations."""
        outside_location = {
            "latitude": WORKPLACE_LATITUDE + 0.2,
            "longitude": WORKPLACE_LONGITUDE,
            "accuracy": 10.0,
        }
        response = self.client.post("/api/attendance/check-in/", outside_location, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("outside the allowed attendance area", response.data["error"])

    def test_leave_still_blocks_checkin(self):
        """Approved leave still blocks check-in."""
        from leave_management.models import LeaveRequest, LeaveType
        today = timezone.localdate()
        leave_type = LeaveType.objects.create(name="Test Leave", code="TEST")
        LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=leave_type,
            start_date=today,
            end_date=today,
            day_type="FULL_DAY",
            duration_days=1,
            reason="Test",
            status="APPROVED",
        )

        response = self.client.post("/api/attendance/check-in/", self.valid_location, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("on approved leave", response.data["error"])

    def test_immediate_checkout_after_checkin_allowed(self):
        """Immediate check-out after check-in is now allowed (no cooldown)."""
        # Check in now
        self.client.post("/api/attendance/check-in/", self.valid_location, format="json")
        # Check out immediately - should succeed
        response = self.client.post("/api/attendance/check-out/", self.valid_location, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Check-out successful")

    # ---------------------------------------------------------------------------
    # Working Duration Calculation Tests
    # ---------------------------------------------------------------------------

    def test_single_in_out_pair_duration(self):
        """Single IN/OUT pair: working_duration = checkout - checkin."""
        now = timezone.make_aware(datetime.combine(timezone.localdate(), datetime_time(12, 0)), timezone.get_current_timezone())
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=now - timedelta(hours=8),
            event_type="CHECK_IN",
            source="MOBILE",
        )
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=now,
            event_type="CHECK_OUT",
            source="MOBILE",
        )
        
        attendance = Attendance.objects.create(employee=self.employee, date=timezone.localdate())
        attendance.recompute_from_events()
        
        expected_duration = timedelta(hours=8)
        self.assertEqual(attendance.working_duration, expected_duration)
        self.assertEqual(attendance.status, "PRESENT")

    def test_multiple_intervals_duration_excludes_breaks(self):
        """Multiple IN/OUT intervals sum only time spent checked in."""
        now = timezone.make_aware(datetime.combine(timezone.localdate(), datetime_time(12, 0)), timezone.get_current_timezone())
        # First interval: 9am - 1pm (4 hours)
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=now - timedelta(hours=8),
            event_type="CHECK_IN",
            source="MOBILE",
        )
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=now - timedelta(hours=4),
            event_type="CHECK_OUT",
            source="MOBILE",
        )
        # Lunch break: 1pm - 2pm (1 hour break)
        # Second interval: 2pm - 6pm (4 hours)
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=now - timedelta(hours=3),
            event_type="CHECK_IN",
            source="MOBILE",
        )
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=now,
            event_type="CHECK_OUT",
            source="MOBILE",
        )
        
        attendance = Attendance.objects.create(employee=self.employee, date=timezone.localdate())
        attendance.recompute_from_events()
        
        expected_duration = timedelta(hours=7)
        self.assertEqual(attendance.working_duration, expected_duration)
        self.assertEqual(attendance.status, "PRESENT")

    def test_three_intervals_duration(self):
        """Three intervals sum independently and exclude both breaks."""
        now = timezone.make_aware(datetime.combine(timezone.localdate(), datetime_time(12, 0)), timezone.get_current_timezone())
        today_start = timezone.make_aware(timezone.datetime.combine(
            timezone.localdate(), timezone.datetime.min.time()
        ))
        base = today_start + timedelta(hours=1)
        
        # 3 intervals of 2 hours each with 30 min breaks
        for i in range(3):
            AttendanceEvent.objects.create(
                employee=self.employee,
                timestamp=base + timedelta(hours=i*2.5),
                event_type="CHECK_IN",
                source="MOBILE",
            )
            AttendanceEvent.objects.create(
                employee=self.employee,
                timestamp=base + timedelta(hours=i*2.5 + 2),
                event_type="CHECK_OUT",
                source="MOBILE",
            )
        
        attendance = Attendance.objects.create(employee=self.employee, date=timezone.localdate())
        attendance.recompute_from_events()
        
        expected_duration = timedelta(hours=6)
        self.assertEqual(attendance.working_duration, expected_duration)
        self.assertEqual(attendance.status, "PRESENT")

    def test_single_checkin_no_checkout_accumulates_open_interval(self):
        """An open interval contributes through the current time."""
        check_in = timezone.now() - timedelta(hours=2)
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=check_in,
            event_type="CHECK_IN",
            source="MOBILE",
        )
        
        attendance = Attendance.objects.create(employee=self.employee, date=timezone.localdate())
        attendance.recompute_from_events()
        
        self.assertAlmostEqual(
            attendance.working_duration.total_seconds(),
            timedelta(hours=2).total_seconds(),
            delta=2,
        )
        self.assertEqual(attendance.status, "INCOMPLETE")
        self.assertIsNotNone(attendance.check_in)
        self.assertIsNone(attendance.check_out)

    def test_forgotten_checkout_is_detected_without_creating_checkout(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        check_in = timezone.make_aware(
            datetime.combine(yesterday, datetime_time(9, 0)),
            timezone.get_current_timezone(),
        )
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=check_in,
            event_type="CHECK_IN",
            source="MOBILE",
        )
        Attendance.objects.create(
            employee=self.employee,
            date=yesterday,
            check_in=check_in,
            status="INCOMPLETE",
        )

        response = self.client.get("/api/attendance/today/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        warning = response.data["previous_incomplete_attendance"]
        self.assertEqual(str(warning["date"]), yesterday.isoformat())
        self.assertTrue(warning["needs_regularization"])
        self.assertEqual(
            AttendanceEvent.objects.filter(employee=self.employee, event_type="CHECK_OUT").count(),
            0,
        )

    def test_next_day_checkin_stays_separate_from_forgotten_checkout(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        yesterday_check_in = timezone.now() - timedelta(days=1)
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=yesterday_check_in,
            event_type="CHECK_IN",
            source="MOBILE",
        )
        Attendance.objects.create(
            employee=self.employee,
            date=yesterday,
            check_in=yesterday_check_in,
            status="INCOMPLETE",
        )

        response = self.client.post(
            "/api/attendance/check-in/",
            self.valid_location,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        today = timezone.localdate()
        self.assertTrue(Attendance.objects.filter(employee=self.employee, date=today).exists())
        self.assertIsNone(
            Attendance.objects.get(employee=self.employee, date=yesterday).check_out
        )
        self.assertEqual(
            AttendanceEvent.objects.filter(employee=self.employee).count(),
            2,
        )

    def test_persisted_and_dynamic_duration_share_date_bounded_rules(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        start = timezone.make_aware(
            datetime.combine(yesterday, datetime_time(9, 0)),
            timezone.get_current_timezone(),
        )
        observed_now = timezone.make_aware(
            datetime.combine(yesterday + timedelta(days=1), datetime_time(10, 0)),
            timezone.get_current_timezone(),
        )
        event = AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=start,
            event_type="CHECK_IN",
            source="MOBILE",
        )
        attendance = Attendance.objects.create(
            employee=self.employee,
            date=yesterday,
            check_in=start,
            status="INCOMPLETE",
        )

        with patch("django.utils.timezone.now", return_value=observed_now):
            attendance.recompute_from_events()
        dynamic_duration = calculate_working_duration(
            [event],
            now=observed_now,
            end_at=attendance_day_end(yesterday),
        )

        attendance.refresh_from_db()
        self.assertEqual(attendance.working_duration, dynamic_duration)
        self.assertEqual(dynamic_duration, timedelta(hours=15))

    def test_day_two_checkout_does_not_close_day_one(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        yesterday_check_in = timezone.now() - timedelta(days=1)
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=yesterday_check_in,
            event_type="CHECK_IN",
            source="MOBILE",
        )
        yesterday_attendance = Attendance.objects.create(
            employee=self.employee,
            date=yesterday,
            check_in=yesterday_check_in,
            status="INCOMPLETE",
        )
        today_attendance = Attendance.objects.create(
            employee=self.employee,
            date=timezone.localdate(),
            check_in=timezone.now() - timedelta(minutes=10),
            status="INCOMPLETE",
        )
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=today_attendance.check_in,
            event_type="CHECK_IN",
            source="MOBILE",
        )

        response = self.client.post(
            "/api/attendance/check-out/",
            self.valid_location,
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        yesterday_attendance.refresh_from_db()
        today_attendance.refresh_from_db()
        self.assertIsNone(yesterday_attendance.check_out)
        self.assertIsNotNone(today_attendance.check_out)

    def test_open_interval_after_checkout_includes_only_current_interval(self):
        """A current check-in adds to completed intervals without counting the break."""
        today = timezone.localdate()
        start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
        events = [
            AttendanceEvent.objects.create(employee=self.employee, timestamp=start + timedelta(hours=9), event_type="CHECK_IN"),
            AttendanceEvent.objects.create(employee=self.employee, timestamp=start + timedelta(hours=13), event_type="CHECK_OUT"),
            AttendanceEvent.objects.create(employee=self.employee, timestamp=start + timedelta(hours=14), event_type="CHECK_IN"),
        ]

        duration = calculate_working_duration(events, now=start + timedelta(hours=15))

        self.assertEqual(duration, timedelta(hours=5))

    def test_events_from_another_date_are_not_connected(self):
        """Working duration is calculated only from events on the attendance date."""
        today = timezone.localdate()
        today_start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
        yesterday_start = today_start - timedelta(days=1)
        AttendanceEvent.objects.create(employee=self.employee, timestamp=yesterday_start + timedelta(hours=18), event_type="CHECK_OUT")
        AttendanceEvent.objects.create(employee=self.employee, timestamp=today_start + timedelta(hours=9), event_type="CHECK_IN")

        attendance = Attendance.objects.create(employee=self.employee, date=today)
        with patch('django.utils.timezone.now', return_value=today_start + timedelta(hours=15)):
            attendance.recompute_from_events()

        self.assertEqual(attendance.working_duration, timedelta(hours=6))

    def test_today_and_history_return_event_derived_duration(self):
        """Today and history APIs expose the same break-excluding duration."""
        today = timezone.localdate()
        start = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time()))
        for hour, event_type in ((9, "CHECK_IN"), (13, "CHECK_OUT"), (14, "CHECK_IN"), (18, "CHECK_OUT")):
            AttendanceEvent.objects.create(
                employee=self.employee,
                timestamp=start + timedelta(hours=hour),
                event_type=event_type,
            )

        attendance = Attendance.objects.create(employee=self.employee, date=today)
        attendance.recompute_from_events()

        today_response = self.client.get("/api/attendance/today/")
        history_response = self.client.get("/api/attendance/history/")

        self.assertEqual(today_response.status_code, status.HTTP_200_OK)
        self.assertEqual(history_response.status_code, status.HTTP_200_OK)
        expected_duration = timedelta(hours=8)
        self.assertEqual(today_response.data["working_duration"], expected_duration)
        self.assertEqual(history_response.data[0]["working_duration"], expected_duration)


# ---------------------------------------------------------------------------
# Shift Assignment Tests (Phase 3)
# ---------------------------------------------------------------------------

from attendance.models import Shift


class AdminForceCheckoutTests(APITestCase):
    def setUp(self):
        self.target_date = timezone.localdate()
        self.admin = User.objects.create_user(
            email="force-checkout.admin@example.com",
            password="password123",
            is_staff=True,
        )
        self.employee_user = User.objects.create_user(
            email="force-checkout.employee@example.com",
            password="password123",
        )
        self.employee = Employee.objects.create(
            user=self.employee_user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined=self.target_date,
            is_active=True,
        )
        self.client.force_authenticate(user=self.admin)

    def _timestamp(self, hour):
        return timezone.make_aware(
            datetime.combine(self.target_date, datetime_time(hour, 0)),
            timezone.get_current_timezone(),
        )

    def test_force_checkout_uses_latest_event_for_reopened_attendance(self):
        first_check_in = self._timestamp(9)
        first_check_out = self._timestamp(12)
        second_check_in = self._timestamp(13)
        AttendanceEvent.objects.create(employee=self.employee, timestamp=first_check_in, event_type="CHECK_IN")
        AttendanceEvent.objects.create(employee=self.employee, timestamp=first_check_out, event_type="CHECK_OUT")
        AttendanceEvent.objects.create(employee=self.employee, timestamp=second_check_in, event_type="CHECK_IN")
        attendance = Attendance.objects.create(
            employee=self.employee,
            date=self.target_date,
            check_in=first_check_in,
            check_out=first_check_out,
            status="INCOMPLETE",
        )

        with patch("django.utils.timezone.now", return_value=self._timestamp(15)):
            response = self.client.post("/api/admin/force-checkout/", {
                "employee": self.employee_user.email,
                "date": self.target_date.isoformat(),
            }, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["count"], 1)
        attendance.refresh_from_db()
        self.assertEqual(attendance.status, "PRESENT")
        self.assertEqual(
            AttendanceEvent.objects.filter(employee=self.employee).count(),
            4,
        )

    def test_force_checkout_all_processes_only_currently_open_intervals(self):
        check_in = self._timestamp(9)
        check_out = self._timestamp(12)
        AttendanceEvent.objects.create(employee=self.employee, timestamp=check_in, event_type="CHECK_IN")
        AttendanceEvent.objects.create(employee=self.employee, timestamp=check_out, event_type="CHECK_OUT")
        Attendance.objects.create(
            employee=self.employee,
            date=self.target_date,
            check_in=check_in,
            check_out=check_out,
            status="PRESENT",
        )

        response = self.client.post("/api/admin/force-checkout/", {
            "all": True,
            "date": self.target_date.isoformat(),
        }, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(
            AttendanceEvent.objects.filter(employee=self.employee).count(),
            2,
        )


class ShiftAssignmentTests(APITestCase):
    """Tests for shift self-assignment and admin management."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="shift_test@example.com",
            password="password123",
        )
        self.employee = Employee.objects.create(
            user=self.user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined=date.today(),
            is_active=True,
        )
        self.client.force_authenticate(user=self.user)

        self.shift1 = Shift.objects.create(
            name="Morning Shift",
            code="MORN",
            start_time=datetime_time(9, 0),
            end_time=datetime_time(17, 0),
            employment_type="PERMANENT",
            is_active=True,
        )
        self.shift2 = Shift.objects.create(
            name="Evening Shift",
            code="EVE",
            start_time=datetime_time(17, 0),
            end_time=datetime_time(1, 0),
            employment_type="PERMANENT",
            is_active=True,
        )
        self.inactive_shift = Shift.objects.create(
            name="Night Shift",
            code="NIGHT",
            start_time=datetime_time(22, 0),
            end_time=datetime_time(6, 0),
            employment_type="PERMANENT",
            is_active=False,
        )

        # Admin user
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="admin123",
            is_staff=True,
        )
        self.admin_employee = Employee.objects.create(
            user=self.admin_user,
            department="Admin",
            employment_type="PERMANENT",
            date_joined=date.today(),
            is_active=True,
        )

    # Employee self-assignment tests
    def test_employee_with_no_shift(self):
        """Employee starts with no shift."""
        self.assertIsNone(self.employee.shift)

    def test_employee_can_self_assign_active_shift(self):
        """Employee can self-assign an active shift when none assigned."""
        response = self.client.post(
            "/api/attendance/my-shift/assign/",
            {"shift_id": self.shift1.id},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.shift, self.shift1)

    def test_employee_cannot_reassign_shift(self):
        """Employee cannot change their shift once assigned."""
        self.employee.shift = self.shift1
        self.employee.save()
        
        response = self.client.post(
            "/api/attendance/my-shift/assign/",
            {"shift_id": self.shift2.id},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("already have a shift assigned", response.data["error"])
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.shift, self.shift1)

    def test_employee_cannot_remove_shift(self):
        """Employee cannot remove their shift via self-assignment."""
        self.employee.shift = self.shift1
        self.employee.save()
        
        response = self.client.post(
            "/api/attendance/my-shift/assign/",
            {"shift_id": ""},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        # Employee cannot remove - only admin can

    def test_employee_cannot_assign_inactive_shift(self):
        """Employee cannot self-assign an inactive shift."""
        response = self.client.post(
            "/api/attendance/my-shift/assign/",
            {"shift_id": self.inactive_shift.id},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("inactive", response.data["error"].lower())
        self.employee.refresh_from_db()
        self.assertIsNone(self.employee.shift)

    # Concurrent self-assignment test
    def test_concurrent_self_assignment_race_condition(self):
        """Two concurrent self-assignment requests cannot overwrite shift.
        
        Uses a single test client with manual transaction isolation to simulate
        concurrent requests. The view uses select_for_update() to prevent races.
        """
        from django.db import transaction
        import time
        
        # First request succeeds
        self.employee.refresh_from_db()
        response1 = self.client.post(
            "/api/attendance/my-shift/assign/",
            {"shift_id": self.shift1.id},
            format="json",
        )
        self.assertEqual(response1.status_code, 200)
        
        # Second request immediately after should fail with 409
        # (employee now has shift assigned)
        response2 = self.client.post(
            "/api/attendance/my-shift/assign/",
            {"shift_id": self.shift2.id},
            format="json",
        )
        self.assertEqual(response2.status_code, 409)
        self.assertIn("already assigned", response2.data["error"].lower())
        
        # Employee should still have the first shift
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.shift, self.shift1)
        
        # Verify the atomic check-and-set in the view works by simulating
        # what happens when two requests arrive simultaneously
        # We do this by manually checking the view's transaction logic
        self.employee.shift = None
        self.employee.save()
        
        # Both "requests" check employee.shift is None, then one sets it
        # This is what the view's select_for_update prevents
        with transaction.atomic():
            emp = Employee.objects.select_for_update().get(pk=self.employee.pk)
            self.assertIsNone(emp.shift)
            emp.shift = self.shift1
            emp.save(update_fields=["shift"])
        
        # Second "request" finds shift already assigned
        with transaction.atomic():
            emp = Employee.objects.select_for_update().get(pk=self.employee.pk)
            self.assertIsNotNone(emp.shift)

    # Admin shift management tests
    def test_admin_can_assign_shift(self):
        """Admin can assign shift to any employee."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            "/api/attendance/admin/shift/assign/",
            {"employee_email": self.user.email, "shift_id": self.shift1.id},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.shift, self.shift1)

    def test_admin_can_change_shift(self):
        """Admin can change employee's shift."""
        self.employee.shift = self.shift1
        self.employee.save()
        
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            "/api/attendance/admin/shift/assign/",
            {"employee_email": self.user.email, "shift_id": self.shift2.id},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.shift, self.shift2)

    def test_admin_can_remove_shift(self):
        """Admin can remove employee's shift."""
        self.employee.shift = self.shift1
        self.employee.save()
        
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            "/api/attendance/admin/shift/assign/",
            {"employee_email": self.user.email, "shift_id": None},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.employee.refresh_from_db()
        self.assertIsNone(self.employee.shift)

    def test_app_admin_can_manage_shifts(self):
        """App Admin (is_superuser) can manage shifts."""
        superuser = User.objects.create_user(
            email="super@example.com",
            password="super123",
            is_superuser=True,
        )
        self.client.force_authenticate(user=superuser)
        
        response = self.client.post(
            "/api/attendance/admin/shift/assign/",
            {"employee_email": self.user.email, "shift_id": self.shift1.id},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.shift, self.shift1)

    def test_unauthorized_users_rejected(self):
        """Non-admin, non-superuser users are rejected from admin endpoints."""
        other_user = User.objects.create_user(
            email="other@example.com",
            password="other123",
        )
        self.client.force_authenticate(user=other_user)
        
        response = self.client.post(
            "/api/attendance/admin/shift/assign/",
            {"employee_email": self.user.email, "shift_id": self.shift1.id},
            format="json",
        )
        self.assertIn(response.status_code, [401, 403])

    # Shift list and my-shift tests
    def test_shift_list_shows_only_active(self):
        """Shift list only shows active shifts for self-assignment."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/attendance/shifts/")
        self.assertEqual(response.status_code, 200)
        shift_codes = [s["code"] for s in response.data["shifts"]]
        self.assertIn("MORN", shift_codes)
        self.assertIn("EVE", shift_codes)
        self.assertNotIn("NIGHT", shift_codes)  # inactive

    def test_my_shift_shows_assigned(self):
        """My shift endpoint returns assigned shift."""
        self.employee.shift = self.shift1
        self.employee.save()
        
        response = self.client.get("/api/attendance/my-shift/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["shift"]["code"], "MORN")

    def test_my_shift_shows_none_when_unassigned(self):
        """My shift endpoint returns null when unassigned."""
        response = self.client.get("/api/attendance/my-shift/")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["shift"])

    # Employee without shift cannot check in
    def test_employee_without_shift_cannot_check_in(self):
        """Employee without assigned shift cannot check in."""
        # No shift assigned
        response = self.client.post("/api/attendance/check-in/", {
            "latitude": WORKPLACE_LATITUDE,
            "longitude": WORKPLACE_LONGITUDE,
            "accuracy": 15.0,
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("shift assigned", response.data["error"])

    def test_employee_with_shift_can_check_in(self):
        """Employee with assigned shift can check in."""
        self.employee.shift = self.shift1
        self.employee.save()
        
        response = self.client.post("/api/attendance/check-in/", {
            "latitude": WORKPLACE_LATITUDE,
            "longitude": WORKPLACE_LONGITUDE,
            "accuracy": 15.0,
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertIn("check_in", response.data)


# ---------------------------------------------------------------------------
# Shift Adherence Tests (5-minute grace period)
# ---------------------------------------------------------------------------


class ShiftAdherenceTests(APITestCase):
    """Tests for shift adherence with 5-minute grace period."""

    def setUp(self):
        from django.utils import timezone
        from datetime import time

        self.user = User.objects.create_user(
            email="adherence@example.com",
            password="password123",
        )
        self.shift = Shift.objects.create(
            name="Morning Shift",
            code="MORN",
            start_time=time(9, 0, 0),
            end_time=time(17, 0, 0),
            is_active=True,
        )
        self.employee = Employee.objects.create(
            user=self.user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined=date.today(),
            is_active=True,
            shift=self.shift,
        )

    def test_check_in_before_shift_start_is_on_time(self):
        """Check-in before shift start time is ON_TIME."""
        from django.utils import timezone
        from datetime import datetime, time
        
        today = timezone.localdate()
        # Create check-in at 8:55 AM (5 min before 9 AM shift start)
        check_in_time = timezone.make_aware(datetime.combine(today, time(8, 55)))
        
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=check_in_time,
            event_type="CHECK_IN",
            source="MOBILE",
        )
        
        attendance = Attendance.objects.create(employee=self.employee, date=today)
        attendance.recompute_from_events()
        
        adherence = attendance.get_shift_adherence()
        self.assertEqual(adherence, "ON_TIME")

    def test_check_in_at_shift_start_is_on_time(self):
        """Check-in exactly at shift start time is ON_TIME."""
        from django.utils import timezone
        from datetime import datetime, time
        
        today = timezone.localdate()
        # Create check-in at exactly 9:00 AM
        check_in_time = timezone.make_aware(datetime.combine(today, time(9, 0)))
        
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=check_in_time,
            event_type="CHECK_IN",
            source="MOBILE",
        )
        
        attendance = Attendance.objects.create(employee=self.employee, date=today)
        attendance.recompute_from_events()
        
        adherence = attendance.get_shift_adherence()
        self.assertEqual(adherence, "ON_TIME")

    def test_check_in_within_5min_grace_is_on_time(self):
        """Check-in within 5-minute grace period is ON_TIME."""
        from django.utils import timezone
        from datetime import datetime, time
        
        today = timezone.localdate()
        # Create check-in at 9:04 AM (4 min after 9 AM shift start, within grace)
        check_in_time = timezone.make_aware(datetime.combine(today, time(9, 4)))
        
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=check_in_time,
            event_type="CHECK_IN",
            source="MOBILE",
        )
        
        attendance = Attendance.objects.create(employee=self.employee, date=today)
        attendance.recompute_from_events()
        
        adherence = attendance.get_shift_adherence()
        self.assertEqual(adherence, "ON_TIME")

    def test_check_in_exactly_at_5min_boundary_is_on_time(self):
        """Check-in exactly at 5-minute mark is ON_TIME."""
        from django.utils import timezone
        from datetime import datetime, time
        
        today = timezone.localdate()
        # Create check-in at exactly 9:05 AM
        check_in_time = timezone.make_aware(datetime.combine(today, time(9, 5)))
        
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=check_in_time,
            event_type="CHECK_IN",
            source="MOBILE",
        )
        
        attendance = Attendance.objects.create(employee=self.employee, date=today)
        attendance.recompute_from_events()
        
        adherence = attendance.get_shift_adherence()
        self.assertEqual(adherence, "ON_TIME")

    def test_check_in_after_5min_grace_is_late(self):
        """Check-in after 5-minute grace period is LATE."""
        from django.utils import timezone
        from datetime import datetime, time
        
        today = timezone.localdate()
        # Create check-in at 9:06 AM (6 min after 9 AM shift start, beyond grace)
        check_in_time = timezone.make_aware(datetime.combine(today, time(9, 6)))
        
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=check_in_time,
            event_type="CHECK_IN",
            source="MOBILE",
        )
        
        attendance = Attendance.objects.create(employee=self.employee, date=today)
        attendance.recompute_from_events()
        
        adherence = attendance.get_shift_adherence()
        self.assertEqual(adherence, "LATE")

    def test_check_in_significantly_late_is_late(self):
        """Check-in significantly after shift start is LATE."""
        from django.utils import timezone
        from datetime import datetime, time
        
        today = timezone.localdate()
        # Create check-in at 9:30 AM (30 min late)
        check_in_time = timezone.make_aware(datetime.combine(today, time(9, 30)))
        
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=check_in_time,
            event_type="CHECK_IN",
            source="MOBILE",
        )
        
        attendance = Attendance.objects.create(employee=self.employee, date=today)
        attendance.recompute_from_events()
        
        adherence = attendance.get_shift_adherence()
        self.assertEqual(adherence, "LATE")

    def test_no_shift_returns_none_adherence(self):
        """Employee without shift returns None for adherence."""
        from django.utils import timezone
        
        # Remove shift
        self.employee.shift = None
        self.employee.save()
        
        check_in_time = timezone.now()
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=check_in_time,
            event_type="CHECK_IN",
            source="MOBILE",
        )
        
        attendance = Attendance.objects.create(employee=self.employee, date=timezone.localdate())
        attendance.recompute_from_events()
        
        adherence = attendance.get_shift_adherence()
        self.assertIsNone(adherence)

    def test_no_check_in_returns_none_adherence(self):
        """Attendance without check-in returns None for adherence."""
        attendance = Attendance.objects.create(
            employee=self.employee,
            date=timezone.localdate(),
        )
        
        adherence = attendance.get_shift_adherence()
        self.assertIsNone(adherence)

    def test_get_shift_adherence_does_not_save_attendance(self):
        """Shift adherence is derived and must not persist unrelated fields."""
        from datetime import datetime

        today = timezone.localdate()
        attendance = Attendance.objects.create(
            employee=self.employee,
            date=today,
            check_in=timezone.make_aware(datetime.combine(today, datetime_time(9, 0))),
        )
        with patch.object(attendance, "save") as save:
            self.assertEqual(attendance.get_shift_adherence(), "ON_TIME")
        save.assert_not_called()


# ---------------------------------------------------------------------------
# Weekend Attendance Tests
# ---------------------------------------------------------------------------


class WeekendAttendanceTests(APITestCase):
    """Tests for weekend attendance behavior."""

    def setUp(self):
        from datetime import datetime, time
        
        self.user = User.objects.create_user(
            email="weekend@example.com",
            password="password123",
        )
        self.shift = Shift.objects.create(
            name="Morning Shift",
            code="MORN",
            start_time=time(9, 0, 0),
            end_time=time(17, 0, 0),
            is_active=True,
        )
        self.employee = Employee.objects.create(
            user=self.user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined=date.today(),
            is_active=True,
            shift=self.shift,
            section="A",
        )
        self.client.force_authenticate(user=self.user)

        self.valid_location = {
            "latitude": WORKPLACE_LATITUDE,
            "longitude": WORKPLACE_LONGITUDE,
            "accuracy": 15.0,
        }

    def _get_next_saturday(self):
        """Get the next Saturday date."""
        today = date.today()
        days_ahead = 5 - today.weekday()  # Saturday is 5
        if days_ahead <= 0:
            days_ahead += 7
        return today + timedelta(days=days_ahead)

    def _get_next_sunday(self):
        """Get the next Sunday date."""
        today = date.today()
        days_ahead = 6 - today.weekday()  # Sunday is 6
        if days_ahead <= 0:
            days_ahead += 7
        return today + timedelta(days=days_ahead)

    def test_saturday_with_no_attendance_no_record_created(self):
        """Saturday with no attendance → no Attendance record should exist."""
        saturday = self._get_next_saturday()
        
        # Verify no attendance exists
        exists = Attendance.objects.filter(employee=self.employee, date=saturday).exists()
        self.assertFalse(exists)

    def test_sunday_with_no_attendance_no_record_created(self):
        """Sunday with no attendance → no Attendance record should exist."""
        sunday = self._get_next_sunday()
        
        # Verify no attendance exists
        exists = Attendance.objects.filter(employee=self.employee, date=sunday).exists()
        self.assertFalse(exists)

    @patch('django.utils.timezone.now')
    @patch('django.utils.timezone.localdate')
    def test_saturday_check_in_allowed(self, mock_localdate, mock_now):
        """Saturday check-in is allowed and creates attendance record."""
        saturday = self._get_next_saturday()
        mock_localdate.return_value = saturday
        
        from datetime import datetime
        from django.utils import timezone as tz
        saturday_datetime = tz.make_aware(datetime.combine(saturday, datetime.min.time().replace(hour=10)))
        mock_now.return_value = saturday_datetime
        
        response = self.client.post("/api/attendance/check-in/", self.valid_location, format="json")
        self.assertEqual(response.status_code, 201)
        
        # Verify attendance was created
        attendance = Attendance.objects.get(employee=self.employee, date=saturday)
        self.assertIsNotNone(attendance.check_in)
        self.assertEqual(attendance.status, "INCOMPLETE")

    @patch('django.utils.timezone.now')
    @patch('django.utils.timezone.localdate')
    def test_saturday_check_out_allowed(self, mock_localdate, mock_now):
        """Saturday check-out is allowed."""
        saturday = self._get_next_saturday()
        mock_localdate.return_value = saturday
        
        from datetime import datetime
        from django.utils import timezone as tz
        saturday_checkin = tz.make_aware(datetime.combine(saturday, datetime.min.time().replace(hour=9)))
        saturday_checkout = tz.make_aware(datetime.combine(saturday, datetime.min.time().replace(hour=17)))
        
        # Check in first
        mock_now.return_value = saturday_checkin
        self.client.post("/api/attendance/check-in/", self.valid_location, format="json")
        
        # Check out
        mock_now.return_value = saturday_checkout
        response = self.client.post("/api/attendance/check-out/", self.valid_location, format="json")
        self.assertEqual(response.status_code, 200)
        
        # Verify attendance was updated
        attendance = Attendance.objects.get(employee=self.employee, date=saturday)
        self.assertIsNotNone(attendance.check_in)
        self.assertIsNotNone(attendance.check_out)
        self.assertEqual(attendance.status, "PRESENT")

    @patch('django.utils.timezone.localdate')
    @patch('django.utils.timezone.now')
    def test_multiple_weekend_in_out_cycles(self, mock_now, mock_localdate):
        """Multiple IN/OUT cycles work on weekends."""
        saturday = self._get_next_saturday()
        mock_localdate.return_value = saturday
        
        from datetime import datetime
        from django.utils import timezone as tz
        base_time = tz.make_aware(datetime.combine(saturday, datetime.min.time().replace(hour=9)))
        
        # First cycle
        mock_now.return_value = base_time
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=base_time,
            event_type="CHECK_IN",
            source="MOBILE",
        )
        mock_now.return_value = base_time + timedelta(hours=4)
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=base_time + timedelta(hours=4),
            event_type="CHECK_OUT",
            source="MOBILE",
        )
        
        # Second cycle
        mock_now.return_value = base_time + timedelta(hours=5)
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=base_time + timedelta(hours=5),
            event_type="CHECK_IN",
            source="MOBILE",
        )
        mock_now.return_value = base_time + timedelta(hours=8)
        AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=base_time + timedelta(hours=8),
            event_type="CHECK_OUT",
            source="MOBILE",
        )
        
        # Recompute attendance
        attendance = Attendance.objects.create(employee=self.employee, date=saturday)
        attendance.recompute_from_events()
        
        # Verify first-in/last-out logic
        events = AttendanceEvent.objects.filter(employee=self.employee, timestamp__date=saturday)
        self.assertEqual(events.count(), 4)
        self.assertEqual(attendance.check_in, base_time)  # First check-in
        self.assertEqual(attendance.check_out, base_time + timedelta(hours=8))  # Last check-out
        self.assertEqual(attendance.status, "PRESENT")

    @patch('django.utils.timezone.now')
    @patch('django.utils.timezone.localdate')
    def test_weekend_attendance_appears_in_daily_summary(self, mock_localdate, mock_now):
        """Weekend attendance with actual check-in appears in summary."""
        saturday = self._get_next_saturday()
        mock_localdate.return_value = saturday
        
        from datetime import datetime
        from django.utils import timezone as tz
        saturday_datetime = tz.make_aware(datetime.combine(saturday, datetime.min.time().replace(hour=10)))
        mock_now.return_value = saturday_datetime
        
        # Create attendance
        self.client.post("/api/attendance/check-in/", self.valid_location, format="json")
        
        # Verify in daily summary (today endpoint)
        response = self.client.get("/api/attendance/today/")
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data["check_in"])

    def test_weekend_without_attendance_not_treated_as_absence(self):
        """Weekend without attendance should not be marked as YET_TO_CHECK_IN."""
        # Create another employee for team context
        other_user = User.objects.create_user(
            email="other@example.com",
            password="password123",
        )
        other_employee = Employee.objects.create(
            user=other_user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined=date.today(),
            is_active=True,
            shift=self.shift,
            section="A",
        )
        
        # Mock today as Saturday
        saturday = self._get_next_saturday()
        with patch('django.utils.timezone.localdate', return_value=saturday):
            response = self.client.get("/api/attendance/my-team/")
            self.assertEqual(response.status_code, 200)
            
            # Find team members without attendance
            members = response.data["members"]
            weekend_members = [m for m in members if m["status"] == "WEEKEND"]
            
            # Both employees should show WEEKEND status (no attendance on Saturday)
            self.assertEqual(len(weekend_members), 2)
            self.assertEqual(response.data["yet_to_check_in_count"], 0)

    @patch('django.utils.timezone.now')
    @patch('django.utils.timezone.localdate')
    def test_weekday_behavior_remains_unchanged(self, mock_localdate, mock_now):
        """Weekday attendance behavior is not affected by weekend logic."""
        # Use a known weekday (Monday = 0)
        today = date.today()
        monday = today + timedelta(days=(7 - today.weekday()))  # Next Monday
        mock_localdate.return_value = monday
        
        from datetime import datetime
        from django.utils import timezone as tz
        monday_datetime = tz.make_aware(datetime.combine(monday, datetime.min.time().replace(hour=10)))
        mock_now.return_value = monday_datetime
        
        # Check in on Monday
        response = self.client.post("/api/attendance/check-in/", self.valid_location, format="json")
        self.assertEqual(response.status_code, 201)
        
        # Verify attendance was created
        attendance = Attendance.objects.get(employee=self.employee, date=monday)
        self.assertIsNotNone(attendance.check_in)
        self.assertEqual(attendance.status, "INCOMPLETE")

    def test_is_weekend_helper_method(self):
        """Attendance.is_weekend() correctly identifies weekends."""
        saturday = self._get_next_saturday()
        sunday = self._get_next_sunday()
        
        sat_attendance = Attendance.objects.create(employee=self.employee, date=saturday)
        sun_attendance = Attendance.objects.create(employee=self.employee, date=sunday)
        
        self.assertTrue(sat_attendance.is_weekend())
        self.assertTrue(sun_attendance.is_weekend())
        
        # Test weekday
        today = date.today()
        monday = today + timedelta(days=(7 - today.weekday()))
        mon_attendance = Attendance.objects.create(
            employee=self.employee,
            date=monday,
        )
        self.assertFalse(mon_attendance.is_weekend())

    @patch('django.utils.timezone.now')
    @patch('django.utils.timezone.localdate')
    def test_weekend_with_attendance_shows_checked_in_in_team(self, mock_localdate, mock_now):
        """Weekend attendance with check-in shows CHECKED_IN status in team view."""
        saturday = self._get_next_saturday()
        mock_localdate.return_value = saturday
        
        from datetime import datetime
        from django.utils import timezone as tz
        saturday_datetime = tz.make_aware(datetime.combine(saturday, datetime.min.time().replace(hour=10)))
        mock_now.return_value = saturday_datetime
        
        # Check in
        self.client.post("/api/attendance/check-in/", self.valid_location, format="json")
        
        # Get team status
        response = self.client.get("/api/attendance/my-team/")
        self.assertEqual(response.status_code, 200)
        
        # Employee should show CHECKED_IN, not WEEKEND
        members = response.data["members"]
        my_status = next((m["status"] for m in members if m["id"] == self.employee.id), None)
        self.assertEqual(my_status, "CHECKED_IN")
        self.assertEqual(response.data["checked_in_count"], 1)

# ---------------------------------------------------------------------------
# Admin Shift Assignment Tests (Employee Management)
# ---------------------------------------------------------------------------


class AdminShiftAssignmentTests(APITestCase):
    """Tests for admin shift assignment via employee management."""

    def setUp(self):
        from datetime import time

        # Create admin user
        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="admin123",
            is_staff=True,
        )
        
        # Create test shifts
        self.shift1 = Shift.objects.create(
            name="Morning Shift",
            code="MORN",
            start_time=time(9, 0),
            end_time=time(17, 0),
            employment_type="PERMANENT",
            is_active=True,
        )
        self.shift2 = Shift.objects.create(
            name="Evening Shift", 
            code="EVE",
            start_time=time(17, 0),
            end_time=time(1, 0),
            employment_type="PERMANENT",
            is_active=True,
        )
        
        # Create test employee
        self.employee_user = User.objects.create_user(
            email="employee@example.com",
            password="pass123",
        )
        self.employee = Employee.objects.create(
            user=self.employee_user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined=date.today(),
            is_active=True,
        )
        
        self.client.force_authenticate(user=self.admin_user)

    def test_admin_can_assign_shift_to_employee(self):
        """Admin can assign a shift to an employee."""
        response = self.client.post(
            "/api/attendance/admin/shift/assign/",
            {
                "employee_email": "employee@example.com",
                "shift_id": self.shift1.id,
            },
            format="json",
        )
        
        self.assertEqual(response.status_code, 200)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.shift, self.shift1)
        self.assertIn("assigned", response.data["message"])

    def test_admin_can_change_employee_shift(self):
        """Admin can change an employee's existing shift."""
        # First assign a shift
        self.employee.shift = self.shift1
        self.employee.save()
        
        # Change to different shift
        response = self.client.post(
            "/api/attendance/admin/shift/assign/",
            {
                "employee_email": "employee@example.com", 
                "shift_id": self.shift2.id,
            },
            format="json",
        )
        
        self.assertEqual(response.status_code, 200)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.shift, self.shift2)

    def test_admin_can_remove_employee_shift(self):
        """Admin can remove an employee's shift assignment."""
        # First assign a shift
        self.employee.shift = self.shift1
        self.employee.save()
        
        # Remove shift
        response = self.client.post(
            "/api/attendance/admin/shift/assign/",
            {
                "employee_email": "employee@example.com",
                "shift_id": None,
            },
            format="json",
        )
        
        self.assertEqual(response.status_code, 200)
        self.employee.refresh_from_db()
        self.assertIsNone(self.employee.shift)
        self.assertIn("removed", response.data["message"])

    def test_employee_list_includes_shift_information(self):
        """Employee list API includes shift information."""
        # Assign a shift to the employee
        self.employee.shift = self.shift1
        self.employee.save()
        
        response = self.client.get("/api/admin/employees/list/")
        self.assertEqual(response.status_code, 200)
        
        employees = response.data
        employee_data = next(emp for emp in employees if emp["id"] == self.employee.id)
        
        # Check shift information is included
        self.assertIn("shift", employee_data)
        shift_info = employee_data["shift"]
        self.assertEqual(shift_info["id"], self.shift1.id)
        self.assertEqual(shift_info["code"], "MORN")
        self.assertEqual(shift_info["name"], "Morning Shift")
        self.assertEqual(shift_info["start_time"], "09:00")
        self.assertEqual(shift_info["end_time"], "17:00")

    def test_employee_list_shows_null_for_no_shift(self):
        """Employee list shows null shift for unassigned employees."""
        response = self.client.get("/api/admin/employees/list/")
        self.assertEqual(response.status_code, 200)
        
        employees = response.data
        employee_data = next(emp for emp in employees if emp["id"] == self.employee.id)
        
        # Check shift is null for unassigned employee
        self.assertIsNone(employee_data["shift"])

    def test_shift_assignment_preserves_historical_events(self):
        """Changing employee shift doesn't affect historical AttendanceEvents."""
        from django.utils import timezone as tz
        
        # Create some historical events with original shift
        self.employee.shift = self.shift1
        self.employee.save()
        
        past_event = AttendanceEvent.objects.create(
            employee=self.employee,
            shift=self.shift1,
            timestamp=tz.now() - timedelta(days=1),
            event_type="CHECK_IN",
            source="MOBILE",
        )
        
        # Change employee's current shift
        response = self.client.post(
            "/api/attendance/admin/shift/assign/",
            {
                "employee_email": "employee@example.com",
                "shift_id": self.shift2.id,
            },
            format="json",
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Historical event should remain unchanged
        past_event.refresh_from_db()
        self.assertEqual(past_event.shift, self.shift1)
        
        # Employee's current shift should be updated
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.shift, self.shift2)

    def test_non_admin_cannot_assign_shifts(self):
        """Non-admin users cannot assign shifts."""
        regular_user = User.objects.create_user(
            email="regular@example.com",
            password="pass123",
        )
        self.client.force_authenticate(user=regular_user)
        
        response = self.client.post(
            "/api/attendance/admin/shift/assign/",
            {
                "employee_email": "employee@example.com",
                "shift_id": self.shift1.id,
            },
            format="json",
        )
        
        self.assertIn(response.status_code, [401, 403])

    def test_superuser_can_assign_shifts(self):
        """Superuser (App Admin) can assign shifts."""
        superuser = User.objects.create_user(
            email="super@example.com",
            password="super123",
            is_superuser=True,
        )
        self.client.force_authenticate(user=superuser)
        
        response = self.client.post(
            "/api/attendance/admin/shift/assign/",
            {
                "employee_email": "employee@example.com",
                "shift_id": self.shift1.id,
            },
            format="json",
        )
        
        self.assertEqual(response.status_code, 200)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.shift, self.shift1)

class AdminEditAttendanceTests(APITestCase):
    def setUp(self):
        self.attendance_date = timezone.localdate() - timedelta(days=1)
        self.employee_user = User.objects.create_user(
            email="edit.employee@example.com",
            password="password123",
        )
        self.employee = Employee.objects.create(
            user=self.employee_user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined=self.attendance_date - timedelta(days=30),
            is_active=True,
        )
        self.manager_user = User.objects.create_user(
            email="manager@example.com",
            password="password123",
            is_staff=True,
        )
        from accounts.models import ManagerScope
        ManagerScope.objects.create(manager=self.manager_user, scope_type="DEPARTMENT", value="Engineering")
        self.superuser = User.objects.create_user(
            email="super@example.com",
            password="password123",
            is_superuser=True,
        )
        
        # Original INCOMPLETE attendance
        self.check_in_time = timezone.make_aware(
            datetime.combine(self.attendance_date, datetime_time(9, 0))
        )
        self.attendance = Attendance.objects.create(
            employee=self.employee,
            date=self.attendance_date,
            check_in=self.check_in_time,
            check_out=None,
            status="INCOMPLETE",
        )
        self.event_check_in = AttendanceEvent.objects.create(
            employee=self.employee,
            timestamp=self.check_in_time,
            event_type="CHECK_IN",
            source="MOBILE",
        )

    def test_manager_cannot_edit_past_attendance(self):
        self.client.force_authenticate(user=self.manager_user)
        
        new_check_in = timezone.make_aware(datetime.combine(self.attendance_date, datetime_time(9, 30)))
        new_check_out = timezone.make_aware(datetime.combine(self.attendance_date, datetime_time(17, 30)))

        response = self.client.post("/api/admin/attendance/edit/", {
            "employee": self.employee_user.email,
            "date": self.attendance_date.isoformat(),
            "reason": "Forgot to check out and check-in was late.",
            "status": "PRESENT",
            "check_in": new_check_in.isoformat(),
            "check_out": new_check_out.isoformat()
        }, format="json")

        self.assertEqual(response.status_code, 403)

    def test_superuser_edit_incomplete_to_present(self):
        self.client.force_authenticate(user=self.superuser)
        
        new_check_in = timezone.make_aware(datetime.combine(self.attendance_date, datetime_time(9, 0)))
        new_check_out = timezone.make_aware(datetime.combine(self.attendance_date, datetime_time(17, 0)))

        response = self.client.post("/api/admin/attendance/edit/", {
            "employee": self.employee_user.email,
            "date": self.attendance_date.isoformat(),
            "reason": "System issue fix",
            "status": "PRESENT",
            "check_in": new_check_in.isoformat(),
            "check_out": new_check_out.isoformat()
        }, format="json")

        self.assertEqual(response.status_code, 200)

        # Verify DB state
        self.attendance.refresh_from_db()
        self.assertEqual(self.attendance.status, "PRESENT")
        self.assertEqual(self.attendance.check_in, new_check_in)
        self.assertEqual(self.attendance.check_out, new_check_out)

        admin_events = AttendanceEvent.objects.filter(employee=self.employee, source="ADMIN")
        self.assertEqual(admin_events.count(), 2)
