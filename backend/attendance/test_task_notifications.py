from datetime import datetime, time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from employees.models import Employee
from notifications.models import Notification

from .models import (
    AttendanceEvent,
    RegularizationRequest,
    RegularizationRequestDay,
)
from .tasks import create_attendance_notification


class AttendanceEventNotificationTaskTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            email="attendance-task@example.test",
        )
        self.employee = Employee.objects.create(
            user=user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined=timezone.localdate(),
        )

    def test_missing_event_returns_without_creating_notification(self):
        self.assertEqual(
            create_attendance_notification.run(-1), "event_not_found"
        )
        self.assertEqual(Notification.objects.count(), 0)

    def test_admin_event_not_duplicated_as_attendance_for_regularization(
        self,
    ):
        target = timezone.localdate()
        timestamp = timezone.make_aware(datetime.combine(target, time(9)))
        with patch("attendance.signals.create_attendance_notification.delay"):
            event = AttendanceEvent.objects.create(
                employee=self.employee,
                timestamp=timestamp,
                event_type="CHECK_IN",
                source="ADMIN",
            )
        RegularizationRequest.objects.create(
            employee=self.employee,
            attendance_date=target,
            request_type="FORGOT_CHECK_IN",
            approved_check_in=timestamp,
            reason="Approved correction",
            status="APPROVED",
        )

        result = create_attendance_notification.run(event.pk)

        self.assertEqual(result, "regularization_correction_skipped")
        self.assertFalse(
            Notification.objects.filter(attendance_event=event).exists()
        )

        grouped_timestamp = timezone.make_aware(
            datetime.combine(target, time(18))
        )
        with patch("attendance.signals.create_attendance_notification.delay"):
            grouped_event = AttendanceEvent.objects.create(
                employee=self.employee,
                timestamp=grouped_timestamp,
                event_type="CHECK_OUT",
                source="ADMIN",
            )
        request = RegularizationRequest.objects.create(
            employee=self.employee,
            attendance_date=target,
            request_type="FORGOT_CHECK_OUT",
            reason="Approved grouped correction",
            status="APPROVED",
        )
        RegularizationRequestDay.objects.create(
            request=request,
            attendance_date=target,
            request_type="FORGOT_CHECK_OUT",
            approved_check_out=grouped_timestamp,
            reason="Approved grouped correction",
        )

        self.assertEqual(
            create_attendance_notification.run(grouped_event.pk),
            "regularization_correction_skipped",
        )
        self.assertFalse(
            Notification.objects.filter(
                attendance_event=grouped_event
            ).exists()
        )

    def test_regular_attendance_event_notification_is_idempotent(self):
        timestamp = timezone.now()
        with patch("attendance.signals.create_attendance_notification.delay"):
            event = AttendanceEvent.objects.create(
                employee=self.employee,
                timestamp=timestamp,
                event_type="CHECK_OUT",
                source="API",
            )

        self.assertEqual(
            create_attendance_notification.run(event.pk), "created"
        )
        self.assertEqual(
            create_attendance_notification.run(event.pk), "already_exists"
        )
        notification = Notification.objects.get(attendance_event=event)
        self.assertEqual(notification.user, self.employee.user)
        self.assertEqual(notification.notification_type, "ATTENDANCE")
        self.assertIn(self.employee.user.email, notification.message)
