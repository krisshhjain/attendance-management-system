from datetime import date, timedelta
from decimal import Decimal

from accounts.models import User
from attendance.models import Attendance
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from employees.models import Employee
from holidays.models import Holiday
from leave_management.models import LeavePolicy, LeaveRequest, LeaveType
from leave_management.services import (
    approve_leave_request,
    calculate_employee_leave_balances,
    calculate_working_days,
    cancel_leave_request,
    deny_leave_request,
    validate_leave_request,
)


class LeaveManagementTestCase(TestCase):
    def setUp(self):
        # Create users
        self.emp_user = User.objects.create_user(
            email="employee@example.com",
            password="password123",
        )
        self.employee = Employee.objects.create(
            user=self.emp_user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined=date(2025, 1, 1),
            is_active=True,
        )

        self.admin_user = User.objects.create_user(
            email="admin@example.com",
            password="password123",
            is_staff=True,
        )

        self.super_admin_user = User.objects.create_user(
            email="superadmin@example.com",
            password="password123",
            is_staff=True,
            is_superuser=True,
        )

        # Create leave types
        self.casual_leave = LeaveType.objects.create(
            name="Casual Leave",
            code="CASUAL",
            is_paid=True,
            allow_half_day=True,
        )
        self.sick_leave = LeaveType.objects.create(
            name="Sick Leave",
            code="SICK",
            is_paid=True,
            requires_document=True,
        )

        # Create leave policies
        self.casual_policy = LeavePolicy.objects.create(
            employee_type="PERMANENT",
            leave_type=self.casual_leave,
            annual_entitlement=Decimal("12.0"),
            effective_from=date(2026, 1, 1),
            is_active=True,
        )
        self.sick_policy = LeavePolicy.objects.create(
            employee_type="PERMANENT",
            leave_type=self.sick_leave,
            annual_entitlement=Decimal("10.0"),
            requires_document=True,
            effective_from=date(2026, 1, 1),
            is_active=True,
        )

    def test_working_days_calculation(self):
        # Monday (2026-09-28) to Friday (2026-10-02) = 5 working days
        start = date(2026, 9, 28)
        end = date(2026, 10, 2)
        days = calculate_working_days(start, end)
        self.assertEqual(days, Decimal("5.0"))

        # Saturday to Sunday = 0 working days
        sat = date(2026, 9, 26)
        sun = date(2026, 9, 27)
        self.assertEqual(calculate_working_days(sat, sun), Decimal("0.0"))

        # Single half-day on Monday
        self.assertEqual(
            calculate_working_days(start, start, "FIRST_HALF"), Decimal("0.5")
        )

    def test_leave_balances_calculation(self):
        balances = calculate_employee_leave_balances(self.employee, year=2026)
        casual = next(b for b in balances if b["leave_type_code"] == "CASUAL")
        self.assertEqual(casual["annual_entitlement"], 12.0)
        self.assertEqual(casual["available"], 12.0)
        self.assertEqual(casual["used"], 0.0)
        self.assertEqual(casual["pending"], 0.0)

    def test_submit_leave_request_and_validation(self):
        # Valid 2-day leave request on Mon-Tue
        start = date(2026, 9, 28)
        end = date(2026, 9, 29)

        duration = validate_leave_request(
            employee=self.employee,
            leave_type=self.casual_leave,
            start_date=start,
            end_date=end,
            reason="Personal work",
        )
        self.assertEqual(duration, Decimal("2.0"))

        req = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.casual_leave,
            start_date=start,
            end_date=end,
            duration_days=duration,
            reason="Personal work",
            status="PENDING",
        )
        self.assertEqual(req.status, "PENDING")

        # Verify attendance is NOT affected while PENDING
        att = Attendance.objects.filter(
            employee=self.employee, date=start
        ).first()
        self.assertIsNone(att)

    def test_approval_workflow_updates_attendance(self):
        start = date(2026, 9, 28)
        end = date(2026, 9, 29)
        req = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.casual_leave,
            start_date=start,
            end_date=end,
            duration_days=Decimal("2.0"),
            reason="Vacation",
            status="PENDING",
        )

        approved = approve_leave_request(
            req, reviewer_user=self.admin_user, remarks="Approved enjoy!"
        )
        self.assertEqual(approved.status, "APPROVED")
        self.assertEqual(approved.reviewed_by, self.admin_user)

        # Check attendance records created with status LEAVE
        att1 = Attendance.objects.get(employee=self.employee, date=start)
        att2 = Attendance.objects.get(employee=self.employee, date=end)
        self.assertEqual(att1.status, "LEAVE")
        self.assertEqual(att2.status, "LEAVE")
        self.assertEqual(att1.leave_request, approved)

    def test_denial_workflow_does_not_affect_attendance(self):
        start = date(2026, 9, 28)
        end = date(2026, 9, 29)
        req = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.casual_leave,
            start_date=start,
            end_date=end,
            duration_days=Decimal("2.0"),
            reason="Vacation",
            status="PENDING",
        )

        denied = deny_leave_request(
            req, reviewer_user=self.admin_user, remarks="Shortage of staff"
        )
        self.assertEqual(denied.status, "DENIED")
        self.assertEqual(denied.reviewer_remarks, "Shortage of staff")

        # Verify no attendance record created
        self.assertFalse(
            Attendance.objects.filter(
                employee=self.employee, date=start
            ).exists()
        )

    def test_overlapping_leave_request_rejected(self):
        start = date(2026, 9, 28)
        end = date(2026, 9, 30)
        LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.casual_leave,
            start_date=start,
            end_date=end,
            duration_days=Decimal("3.0"),
            reason="Trip",
            status="APPROVED",
        )

        with self.assertRaises(ValidationError):
            validate_leave_request(
                employee=self.employee,
                leave_type=self.casual_leave,
                start_date=date(2026, 9, 29),
                end_date=date(2026, 10, 1),
                reason="Overlap",
            )

    def test_employee_cancel_pending_leave(self):
        start = timezone.localdate() + timedelta(days=1)
        end = start + timedelta(days=1)
        req = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.casual_leave,
            start_date=start,
            end_date=end,
            duration_days=Decimal("2.0"),
            reason="Test",
            status="PENDING",
        )
        cancelled = cancel_leave_request(req, user=self.emp_user)
        self.assertEqual(cancelled.status, "CANCELLED")

    def test_employee_cancel_future_approved_leave(self):
        start = timezone.localdate() + timedelta(days=2)
        end = start + timedelta(days=2)
        req = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.casual_leave,
            start_date=start,
            end_date=end,
            duration_days=Decimal("2.0"),
            reason="Test",
            status="APPROVED",
        )
        cancelled = cancel_leave_request(req, user=self.emp_user)
        self.assertEqual(cancelled.status, "CANCELLED")

    def test_employee_can_cancel_past_approved_leave(self):
        start = timezone.localdate() - timedelta(days=2)
        end = start + timedelta(days=2)
        req = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.casual_leave,
            start_date=start,
            end_date=end,
            duration_days=Decimal("2.0"),
            reason="Test",
            status="APPROVED",
        )
        cancelled = cancel_leave_request(req, user=self.emp_user)
        self.assertEqual(cancelled.status, "CANCELLED")

    def test_cancel_already_cancelled(self):
        start = timezone.localdate() + timedelta(days=2)
        end = start + timedelta(days=2)
        req = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.casual_leave,
            start_date=start,
            end_date=end,
            duration_days=Decimal("2.0"),
            reason="Test",
            status="CANCELLED",
        )
        with self.assertRaises(ValidationError):
            cancel_leave_request(req, user=self.emp_user)

    def test_cancel_removes_attendance(self):
        # Admin approves, attendance created
        start = timezone.localdate() + timedelta(days=2)
        from config.business_rules import is_working_day

        if not is_working_day(start):  # Ensure it's a weekday for attendance
            start += timedelta(days=2)
        end = start

        req = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.casual_leave,
            start_date=start,
            end_date=end,
            duration_days=Decimal("1.0"),
            reason="Test",
            status="PENDING",
        )
        approved = approve_leave_request(
            req, reviewer_user=self.admin_user, remarks="OK"
        )

        # Verify attendance exists
        self.assertTrue(
            Attendance.objects.filter(leave_request=approved).exists()
        )

        # Employee cancels future approved leave
        cancel_leave_request(approved, user=self.emp_user)

        # Verify attendance removed
        self.assertFalse(
            Attendance.objects.filter(leave_request=approved).exists()
        )

    def test_validation_rejects_inactive_employee_and_inactive_leave_type(
        self,
    ):
        self.employee.is_active = False
        with self.assertRaises(ValidationError) as employee_error:
            validate_leave_request(
                self.employee,
                self.casual_leave,
                date(2026, 9, 28),
                date(2026, 9, 28),
            )
        self.assertIn("Inactive employee", str(employee_error.exception))

        self.employee.is_active = True
        self.sick_leave.is_active = False
        with self.assertRaises(ValidationError) as type_error:
            validate_leave_request(
                self.employee,
                self.sick_leave,
                date(2026, 9, 28),
                date(2026, 9, 28),
            )
        self.assertIn("currently inactive", str(type_error.exception))

    def test_validation_rejects_weekends_half_days_and_missing_documents(self):
        weekend = timezone.localdate() + timedelta(days=1)
        while weekend.weekday() != 5:
            weekend += timedelta(days=1)
        with self.assertRaises(ValidationError) as weekend_error:
            validate_leave_request(
                self.employee,
                self.casual_leave,
                weekend,
                weekend + timedelta(days=1),
            )
        self.assertIn("no working days", str(weekend_error.exception))

        self.sick_leave.allow_half_day = False
        workday = weekend + timedelta(days=2)
        with self.assertRaises(ValidationError) as half_day_error:
            validate_leave_request(
                self.employee,
                self.sick_leave,
                workday,
                workday,
                day_type="FIRST_HALF",
            )
        self.assertIn(
            "Half-day leave is not allowed", str(half_day_error.exception)
        )

        self.sick_leave.allow_half_day = True
        self.sick_leave.requires_document = True
        with self.assertRaises(ValidationError) as document_error:
            validate_leave_request(
                self.employee,
                self.sick_leave,
                workday,
                workday,
                attachment="",
            )
        self.assertIn(
            "Supporting documentation is required",
            str(document_error.exception),
        )

    def test_leave_policy_enforces_notice_and_consecutive_day_limits(self):
        self.casual_policy.min_notice_days = 5
        self.casual_policy.save(update_fields=["min_notice_days"])
        start = timezone.localdate() + timedelta(days=2)
        while start.weekday() >= 5:
            start += timedelta(days=1)

        with self.assertRaises(ValidationError) as notice_error:
            validate_leave_request(
                self.employee,
                self.casual_leave,
                start,
                start,
                reason="Personal",
            )
        self.assertIn("Minimum notice period", str(notice_error.exception))

        self.casual_policy.min_notice_days = 0
        self.casual_policy.max_consecutive_days = 1
        self.casual_policy.save(
            update_fields=["min_notice_days", "max_consecutive_days"]
        )
        start += timedelta(days=(7 - start.weekday()) % 7)
        end = start + timedelta(days=1)
        with self.assertRaises(ValidationError) as duration_error:
            validate_leave_request(
                self.employee,
                self.casual_leave,
                start,
                end,
                reason="Personal",
            )
        self.assertIn(
            "Maximum consecutive days", str(duration_error.exception)
        )

    def test_denial_without_reviewer_remarks_preserves_pending_request(self):
        target = timezone.localdate() + timedelta(days=3)
        while target.weekday() >= 5:
            target += timedelta(days=1)
        request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.casual_leave,
            start_date=target,
            end_date=target,
            duration_days=Decimal("1.0"),
            reason="Personal",
            status="PENDING",
        )

        with self.assertRaises(ValidationError) as raised:
            deny_leave_request(request, self.admin_user, "  ")

        self.assertIn("Reviewer remarks are required", str(raised.exception))
        request.refresh_from_db()
        self.assertEqual(request.status, "PENDING")
        self.assertFalse(
            Attendance.objects.filter(leave_request=request).exists()
        )

    def test_approval_rechecks_dates_after_a_holiday_is_added(self):
        target = timezone.localdate() + timedelta(days=7)
        while target.weekday() >= 5:
            target += timedelta(days=1)
        request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.casual_leave,
            start_date=target,
            end_date=target,
            duration_days=Decimal("1.0"),
            reason="Personal",
            status="PENDING",
        )
        Holiday.objects.create(date=target, name="New company holiday")

        with self.assertRaises(ValidationError) as raised:
            approve_leave_request(request, self.admin_user)

        self.assertIn("no working days", str(raised.exception))
        request.refresh_from_db()
        self.assertEqual(request.status, "PENDING")
        self.assertFalse(
            Attendance.objects.filter(leave_request=request).exists()
        )
