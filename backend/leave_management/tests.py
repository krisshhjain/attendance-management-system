from datetime import date, timedelta
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from attendance.models import Attendance
from employees.models import Employee
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
        self.assertEqual(calculate_working_days(start, start, "FIRST_HALF"), Decimal("0.5"))

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
        att = Attendance.objects.filter(employee=self.employee, date=start).first()
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

        approved = approve_leave_request(req, reviewer_user=self.admin_user, remarks="Approved enjoy!")
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

        denied = deny_leave_request(req, reviewer_user=self.admin_user, remarks="Shortage of staff")
        self.assertEqual(denied.status, "DENIED")
        self.assertEqual(denied.reviewer_remarks, "Shortage of staff")

        # Verify no attendance record created
        self.assertFalse(Attendance.objects.filter(employee=self.employee, date=start).exists())

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
