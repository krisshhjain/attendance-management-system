from datetime import date, datetime, time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from attendance.models import Attendance
from attendance.tasks import check_consecutive_absences
from employees.models import Employee
from leave_management.models import LeaveRequest, LeaveType
from notifications.models import Notification
from holidays.models import Holiday


User = get_user_model()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class ConsecutiveAbsenceTaskTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            email="manager@example.com",
            password="password123",
            is_system_admin=True,
        )
        self.employee_user = User.objects.create_user(
            email="employee@example.com",
            password="password123",
        )
        self.employee = Employee.objects.create(
            user=self.employee_user,
            department="Operations",
            employment_type="PERMANENT",
            date_joined=date(2026, 1, 1),
        )

    def run_task(self, evaluation_date):
        with self.captureOnCommitCallbacks(execute=True):
            return check_consecutive_absences.run(run_date=evaluation_date)

    def mark_attendance(self, target_date):
        timestamp = timezone.make_aware(datetime.combine(target_date, time(9)))
        Attendance.objects.create(
            employee=self.employee,
            date=target_date,
            check_in=timestamp,
            status="INCOMPLETE",
        )

    def test_one_absent_required_day_does_not_alert(self):
        self.mark_attendance(date(2026, 9, 28))

        self.run_task(date(2026, 9, 30))

        self.assertFalse(Notification.objects.filter(notification_type="ABSENCE_ALERT").exists())

    @patch("notifications.services.send_notification_email.delay")
    def test_two_consecutive_required_days_alert_manager_and_queue_email(self, delay):
        with self.captureOnCommitCallbacks(execute=True):
            result = check_consecutive_absences.run(run_date=date(2026, 9, 30))

        alert = Notification.objects.get(notification_type="ABSENCE_ALERT")
        self.assertEqual(alert.user, self.manager)
        self.assertEqual(result["alerts_created"], 1)
        delay.assert_called_once()

    def test_approved_leave_prevents_alert(self):
        leave_type = LeaveType.objects.create(
            name="Annual Leave",
            code="AL",
            is_active=True,
        )
        LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=leave_type,
            start_date=date(2026, 9, 29),
            end_date=date(2026, 9, 29),
            duration_days=1,
            reason="Approved leave",
            status="APPROVED",
        )

        self.run_task(date(2026, 10, 1))

        self.assertFalse(Notification.objects.filter(notification_type="ABSENCE_ALERT").exists())

    def test_friday_and_monday_absence_alerts(self):
        # Evaluation on Tuesday selects Monday and Friday as the two required days.
        self.run_task(date(2026, 9, 29))

        self.assertTrue(
            Notification.objects.filter(notification_type="ABSENCE_ALERT").exists()
        )

    def test_active_holiday_is_skipped_when_selecting_recent_required_dates(self):
        Holiday.objects.create(date=date(2026, 10, 5), name="Monday holiday")
        result = self.run_task(date(2026, 10, 6))
        self.assertEqual(result["first_absence_date"], "2026-10-01")
        self.assertEqual(result["second_absence_date"], "2026-10-02")
        self.assertTrue(Notification.objects.filter(notification_type="ABSENCE_ALERT").exists())

    def test_friday_and_tuesday_absence_with_monday_attendance_does_not_alert(self):
        # Evaluation on Wednesday selects Tuesday and Monday; Friday is outside
        # the two most recent required attendance days.
        self.mark_attendance(date(2026, 9, 28))
        self.run_task(date(2026, 9, 30))

        self.assertFalse(
            Notification.objects.filter(notification_type="ABSENCE_ALERT").exists()
        )

    def test_rerunning_same_period_is_idempotent(self):
        self.run_task(date(2026, 9, 30))
        self.run_task(date(2026, 9, 30))

        self.assertEqual(
            Notification.objects.filter(notification_type="ABSENCE_ALERT").count(),
            1,
        )

    def test_inactive_employee_is_ignored(self):
        self.employee.is_active = False
        self.employee.save(update_fields=["is_active"])

        self.run_task(date(2026, 9, 30))

        self.assertFalse(Notification.objects.filter(notification_type="ABSENCE_ALERT").exists())

    def test_multiple_managers_receive_alerts(self):
        second_manager = User.objects.create_user(
            email="manager-two@example.com",
            password="password123",
            is_system_admin=True,
        )

        self.run_task(date(2026, 9, 30))

        recipients = set(
            Notification.objects.filter(notification_type="ABSENCE_ALERT")
            .values_list("user__email", flat=True)
        )
        self.assertEqual(recipients, {self.manager.email, second_manager.email})
