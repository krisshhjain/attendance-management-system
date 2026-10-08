from datetime import date, datetime, timezone as datetime_timezone
from datetime import time as datetime_time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from attendance.models import Attendance, AttendanceEvent, RegularizationRequest, Shift
from employees.models import Employee
from leave_management.models import LeaveRequest, LeaveType
from leave_management.services import approve_leave_request, calculate_working_days
from .models import Holiday
from .services import attendance_required, is_company_holiday, is_weekend, is_working_day


User = get_user_model()


class HolidayManagementApiTests(APITestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser("holiday.admin@example.com", "password123")
        self.manager = User.objects.create_user("holiday.manager@example.com", "password123", is_system_admin=True)
        self.employee = User.objects.create_user("holiday.employee@example.com", "password123")
        self.staff = User.objects.create_user("holiday.staff@example.com", "password123", is_staff=True)
        self.admin_url = "/api/holidays/admin/"
        self.read_url = "/api/holidays/"

    def test_superuser_can_create_holiday(self):
        self.client.force_authenticate(self.superuser)
        response = self.client.post(self.admin_url, {"date": "2026-12-25", "name": "Christmas"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Holiday.objects.get().date, date(2026, 12, 25))

    def test_non_superusers_cannot_create_update_or_delete(self):
        holiday = Holiday.objects.create(date=date(2026, 12, 25), name="Christmas")
        for user in (self.manager, self.employee, self.staff):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.post(self.admin_url, {"date": "2026-12-26", "name": "Boxing Day"}, format="json").status_code, 403)
            self.assertEqual(self.client.patch(f"{self.admin_url}{holiday.pk}/", {"name": "Changed"}, format="json").status_code, 403)
            self.assertEqual(self.client.delete(f"{self.admin_url}{holiday.pk}/").status_code, 403)
        self.assertEqual(Holiday.objects.get(pk=holiday.pk).name, "Christmas")

    def test_duplicate_date_is_rejected(self):
        Holiday.objects.create(date=date(2026, 12, 25), name="Christmas")
        self.client.force_authenticate(self.superuser)
        response = self.client.post(self.admin_url, {"date": "2026-12-25", "name": "Another holiday"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("date", response.data)

    def test_malformed_and_missing_holiday_fields_are_rejected_by_api(self):
        self.client.force_authenticate(self.superuser)
        invalid_payloads = [
            {},
            {"date": "not-a-date", "name": "Invalid date"},
            {"date": "2026-12-25"},
            {"date": "2026-12-25", "name": "   "},
            {"date": "2026-12-25", "name": "Holiday", "is_active": "not-a-boolean"},
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = self.client.post(self.admin_url, payload, format="json")
                self.assertEqual(response.status_code, 400)
        self.assertFalse(Holiday.objects.exists())

    def test_superuser_can_edit_holiday(self):
        holiday = Holiday.objects.create(date=date(2026, 12, 25), name="Christmas")
        self.client.force_authenticate(self.superuser)
        response = self.client.patch(f"{self.admin_url}{holiday.pk}/", {"name": "Christmas Day"}, format="json")
        self.assertEqual(response.status_code, 200)
        holiday.refresh_from_db()
        self.assertEqual(holiday.name, "Christmas Day")

    def test_superuser_can_activate_and_deactivate_without_deleting(self):
        holiday = Holiday.objects.create(date=date(2026, 12, 25), name="Christmas")
        self.client.force_authenticate(self.superuser)
        response = self.client.patch(f"{self.admin_url}{holiday.pk}/", {"is_active": False}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Holiday.objects.count(), 1)
        holiday.refresh_from_db()
        self.assertFalse(holiday.is_active)
        self.assertEqual(self.client.patch(f"{self.admin_url}{holiday.pk}/", {"is_active": True}, format="json").status_code, 200)

    def test_authenticated_users_can_read_active_holidays_but_not_inactive(self):
        Holiday.objects.create(date=date(2026, 12, 25), name="Christmas")
        Holiday.objects.create(date=date(2026, 12, 26), name="Inactive", is_active=False)
        for user in (self.superuser, self.manager, self.employee, self.staff):
            self.client.force_authenticate(user)
            response = self.client.get(self.read_url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual([(row["date"], row["name"], row["is_active"]) for row in response.data], [("2026-12-25", "Christmas", True)])

    def test_active_read_requires_authentication(self):
        self.assertEqual(self.client.get(self.read_url).status_code, 401)

    def test_admin_list_includes_inactive_records(self):
        Holiday.objects.create(date=date(2026, 12, 25), name="Christmas", is_active=False)
        self.client.force_authenticate(self.superuser)
        response = self.client.get(self.admin_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertFalse(response.data[0]["is_active"])


class HolidayResolverTests(TestCase):
    def test_weekend_and_company_holiday_are_distinct(self):
        weekday = date(2026, 10, 5)  # Monday
        saturday = date(2026, 10, 3)
        sunday = date(2026, 10, 4)
        Holiday.objects.create(date=weekday, name="Company holiday")
        Holiday.objects.create(date=saturday, name="Weekend holiday")

        self.assertFalse(is_weekend(weekday))
        self.assertTrue(is_company_holiday(weekday))
        self.assertFalse(is_working_day(weekday))
        self.assertFalse(attendance_required(weekday))
        self.assertTrue(is_weekend(saturday))
        self.assertFalse(is_company_holiday(sunday))
        self.assertFalse(is_working_day(saturday))
        self.assertFalse(is_working_day(sunday))
        self.assertTrue(is_company_holiday(saturday))

    def test_resolver_normal_weekday_and_inactive_holiday(self):
        weekday = date(2026, 10, 6)
        inactive_day = date(2026, 10, 7)
        Holiday.objects.create(date=inactive_day, name="Inactive", is_active=False)

        self.assertFalse(is_weekend(weekday))
        self.assertFalse(is_company_holiday(weekday))
        self.assertTrue(is_working_day(weekday))
        self.assertTrue(attendance_required(weekday))
        self.assertFalse(is_company_holiday(inactive_day))
        self.assertTrue(is_working_day(inactive_day))

    @override_settings(TIME_ZONE="America/Los_Angeles", USE_TZ=True)
    def test_date_only_holiday_does_not_shift_at_timezone_boundaries(self):
        holiday_date = date(2026, 1, 1)
        holiday = Holiday.objects.create(date=holiday_date, name="New Year")
        serialized = holiday.date.isoformat()
        boundary_instant = datetime(2026, 1, 1, 0, 30, tzinfo=datetime_timezone.utc)

        self.assertEqual(serialized, "2026-01-01")
        self.assertEqual(boundary_instant.date(), holiday.date)
        self.assertTrue(is_company_holiday(holiday_date))
        self.assertFalse(is_company_holiday(date(2025, 12, 31)))

    def test_empty_or_whitespace_name_is_rejected(self):
        with self.assertRaises(Exception):
            Holiday.objects.create(date=date(2026, 11, 1), name="   ")


class HolidayAttendanceIntegrationTests(APITestCase):
    holiday_date = date(2026, 10, 5)  # Monday

    def setUp(self):
        self.admin = User.objects.create_superuser("holiday.integration.admin@example.com", "password123")
        self.employee_user = User.objects.create_user("holiday.integration.employee@example.com", "password123")
        self.employee = Employee.objects.create(
            user=self.employee_user,
            department="Operations",
            employment_type="PERMANENT",
            date_joined=date(2026, 1, 1),
            section="A",
        )

    def test_daily_attendance_classifies_holiday_weekend_and_required_weekday(self):
        Holiday.objects.create(date=self.holiday_date, name="Company Day")
        self.client.force_authenticate(self.admin)
        holiday = self.client.get(f"/api/admin/attendance/?date={self.holiday_date.isoformat()}")
        saturday = self.client.get("/api/admin/attendance/?date=2026-10-03")
        weekday = self.client.get("/api/admin/attendance/?date=2026-10-06")

        self.assertEqual(holiday.data[0]["status"], "HOLIDAY")
        self.assertEqual(holiday.data[0]["holiday_name"], "Company Day")
        self.assertFalse(holiday.data[0]["attendance_required"])
        self.assertEqual(saturday.data[0]["status"], "WEEKEND")
        self.assertFalse(saturday.data[0]["attendance_required"])
        self.assertEqual(weekday.data[0]["status"], "ABSENT")
        self.assertTrue(weekday.data[0]["attendance_required"])

    def test_inactive_holiday_does_not_suppress_daily_absence(self):
        Holiday.objects.create(date=self.holiday_date, name="Inactive", is_active=False)
        self.client.force_authenticate(self.admin)
        response = self.client.get(f"/api/admin/attendance/?date={self.holiday_date.isoformat()}")
        self.assertEqual(response.data[0]["status"], "ABSENT")
        self.assertTrue(response.data[0]["attendance_required"])

    def test_historical_absent_record_is_presented_as_holiday_in_history_and_dashboard(self):
        Holiday.objects.create(date=self.holiday_date, name="Company Day")
        Attendance.objects.create(employee=self.employee, date=self.holiday_date, status="ABSENT")
        self.client.force_authenticate(self.admin)
        history = self.client.get("/api/attendance/history/")
        self.assertEqual(history.data[0]["status"], "HOLIDAY")
        with patch("attendance.views.timezone.localdate", return_value=self.holiday_date):
            dashboard = self.client.get("/api/admin/dashboard/")
        self.assertEqual(dashboard.data["attendance"][0]["status"], "HOLIDAY")

    def test_admin_cannot_create_new_absent_status_on_holiday(self):
        Holiday.objects.create(date=self.holiday_date, name="Company Day")
        self.client.force_authenticate(self.admin)
        with patch("attendance.views.timezone.localdate", return_value=date(2026, 10, 6)):
            response = self.client.post("/api/admin/attendance/edit/", {
                "employee": self.employee_user.email,
                "date": self.holiday_date.isoformat(),
                "reason": "Correction",
                "status": "ABSENT",
            }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("holiday", response.data["error"])

    def test_team_and_dashboard_expose_holiday_without_counting_missing(self):
        Holiday.objects.create(date=self.holiday_date, name="Company Day")
        peer_user = User.objects.create_user("holiday.integration.peer@example.com", "password123")
        Employee.objects.create(
            user=peer_user, department="Operations", employment_type="PERMANENT",
            date_joined=date(2026, 1, 1), section="A",
        )
        self.client.force_authenticate(self.employee_user)
        with patch("attendance.views.timezone.localdate", return_value=self.holiday_date):
            team = self.client.get("/api/attendance/my-team/")
        self.assertEqual({row["status"] for row in team.data["members"]}, {"HOLIDAY"})
        self.assertEqual(team.data["yet_to_check_in_count"], 0)

        self.client.force_authenticate(self.admin)
        with patch("attendance.views.timezone.localdate", return_value=self.holiday_date):
            dashboard = self.client.get("/api/admin/dashboard/")
        self.assertEqual(dashboard.data["day_type"], "HOLIDAY")
        self.assertEqual(dashboard.data["holiday_name"], "Company Day")
        self.assertFalse(dashboard.data["attendance_required"])

    def test_regularization_rejects_active_holiday_but_not_inactive_holiday(self):
        Holiday.objects.create(date=self.holiday_date, name="Company Day")
        self.client.force_authenticate(self.employee_user)
        payload = {
            "period_type": "DAY",
            "days": [{
                "attendance_date": self.holiday_date.isoformat(),
                "request_type": "FORGOT_CHECK_IN",
                "requested_check_in": "2026-10-05T09:00:00+05:30",
                "reason": "Correction",
            }],
        }
        with patch("attendance.views.timezone.localdate", return_value=date(2026, 10, 6)):
            response = self.client.post("/api/attendance/regularization/", payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("company holidays", response.data["error"])

        Holiday.objects.filter(date=self.holiday_date).update(is_active=False)
        with patch("attendance.views.timezone.localdate", return_value=date(2026, 10, 6)):
            inactive_response = self.client.post("/api/attendance/regularization/", payload, format="json")
        self.assertEqual(inactive_response.status_code, 201, inactive_response.data)

    def test_pending_regularization_cannot_be_approved_after_date_becomes_holiday(self):
        self.client.force_authenticate(self.employee_user)
        timestamp = timezone.make_aware(datetime.combine(date(2026, 10, 5), datetime_time(9)))
        payload = {
            "period_type": "DAY",
            "days": [{
                "attendance_date": self.holiday_date.isoformat(),
                "request_type": "FORGOT_CHECK_IN",
                "requested_check_in": timestamp.isoformat(),
                "reason": "Correction",
            }],
        }
        now = timezone.make_aware(datetime.combine(date(2026, 10, 6), datetime_time(12)))
        with patch("attendance.views.timezone.localdate", return_value=date(2026, 10, 6)), \
             patch("django.utils.timezone.now", return_value=now):
            created = self.client.post("/api/attendance/regularization/", payload, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        Holiday.objects.create(date=self.holiday_date, name="Added after submission")
        request_id = created.data["request_id"]
        request_day = RegularizationRequest.objects.get(pk=request_id).days.get()

        self.client.force_authenticate(self.admin)
        approval_payload = {"days": [{
            "id": request_day.id,
            "check_in": timestamp.isoformat(),
        }]}
        with patch("django.utils.timezone.now", return_value=now):
            approved = self.client.post(
                f"/api/attendance/admin/regularization/{request_id}/approve/",
                approval_payload,
                format="json",
            )
        self.assertEqual(approved.status_code, 400)
        self.assertIn("company holiday", approved.data["error"])
        self.assertEqual(RegularizationRequest.objects.get(pk=request_id).status, "PENDING")

    def test_employee_can_voluntarily_check_in_on_holiday_even_if_stale_absent_exists(self):
        Holiday.objects.create(date=self.holiday_date, name="Company Day")
        shift = Shift.objects.create(
            name="Morning", code="HOL-MORNING", start_time=datetime_time(9), end_time=datetime_time(18),
        )
        self.employee.shift = shift
        self.employee.save(update_fields=["shift"])
        Attendance.objects.create(employee=self.employee, date=self.holiday_date, status="ABSENT")
        self.client.force_authenticate(self.employee_user)
        timestamp = timezone.make_aware(datetime.combine(self.holiday_date, datetime_time(9)))
        with patch("attendance.views.timezone.localdate", return_value=self.holiday_date), \
             patch("attendance.views.timezone.now", return_value=timestamp), \
             patch("attendance.views.validate_attendance_geofence", return_value=(True, None, 0, (0, 0, 5))):
            response = self.client.post("/api/attendance/check-in/", {"latitude": 0, "longitude": 0, "accuracy": 5}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(AttendanceEvent.objects.filter(employee=self.employee, timestamp=timestamp, event_type="CHECK_IN").exists())


class HolidayLeaveIntegrationTests(TestCase):
    def setUp(self):
        user = User.objects.create_user("holiday.leave.employee@example.com", "password123")
        self.employee = Employee.objects.create(
            user=user, department="Operations", employment_type="PERMANENT", date_joined=date(2026, 1, 1),
        )
        self.reviewer = User.objects.create_superuser("holiday.leave.admin@example.com", "password123")
        self.leave_type = LeaveType.objects.create(name="Annual", code="HOLIDAY-AL", is_paid=False)

    def test_leave_duration_half_day_and_approval_skip_holiday_date(self):
        Holiday.objects.create(date=date(2026, 10, 7), name="Midweek holiday")
        self.assertEqual(calculate_working_days(date(2026, 10, 5), date(2026, 10, 9)), 4)
        self.assertEqual(calculate_working_days(date(2026, 10, 7), date(2026, 10, 7), "FIRST_HALF"), 0)
        request = LeaveRequest.objects.create(
            employee=self.employee, leave_type=self.leave_type,
            start_date=date(2026, 10, 5), end_date=date(2026, 10, 9),
            duration_days=4, reason="Leave", status="PENDING",
        )
        approve_leave_request(request, self.reviewer)
        self.assertEqual(
            set(Attendance.objects.filter(leave_request=request).values_list("date", flat=True)),
            {date(2026, 10, 5), date(2026, 10, 6), date(2026, 10, 8), date(2026, 10, 9)},
        )

    def test_pending_leave_is_recalculated_when_holiday_added_after_submission(self):
        request = LeaveRequest.objects.create(
            employee=self.employee, leave_type=self.leave_type,
            start_date=date(2026, 10, 5), end_date=date(2026, 10, 7),
            duration_days=3, reason="Leave", status="PENDING",
        )
        Holiday.objects.create(date=date(2026, 10, 6), name="Added later")
        approved = approve_leave_request(request, self.reviewer)
        self.assertEqual(approved.duration_days, 2)
        self.assertFalse(Attendance.objects.filter(leave_request=request, date=date(2026, 10, 6)).exists())

    def test_previously_approved_leave_duration_remains_a_snapshot(self):
        request = LeaveRequest.objects.create(
            employee=self.employee, leave_type=self.leave_type,
            start_date=date(2026, 10, 5), end_date=date(2026, 10, 7),
            duration_days=3, reason="Already approved", status="APPROVED",
        )
        Holiday.objects.create(date=date(2026, 10, 6), name="Added later")
        request.refresh_from_db()
        self.assertEqual(request.duration_days, 3)

    def test_working_day_calculation_across_month_and_year_boundary(self):
        Holiday.objects.create(date=date(2026, 12, 31), name="Year end")
        Holiday.objects.create(date=date(2027, 1, 1), name="New year")
        self.assertEqual(calculate_working_days(date(2026, 12, 30), date(2027, 1, 4)), 2)
