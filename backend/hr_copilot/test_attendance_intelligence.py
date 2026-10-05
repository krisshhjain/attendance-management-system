from datetime import time as datetime_time
from accounts.models import ManagerScope
from datetime import datetime, timedelta, time as datetime_time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from attendance.models import Attendance, AttendanceEvent, Shift
from employees.models import Employee
from hr_copilot.services.attendance_intelligence import attendance_intelligence
from hr_copilot.services.pipeline import analyze_question


class AttendanceIntelligenceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email="copilot-intelligence-admin@example.test",
            is_system_admin=True,
            
            
        )
        ManagerScope.objects.create(manager=self.admin, scope_type='SECTION', value='C')
        ManagerScope.objects.create(manager=self.admin, scope_type='DEPARTMENT', value='Engineering')

        today = timezone.localdate()
        # Guarantee a Wednesday so today, today-1, etc. are all working days
        while today.weekday() != 2:
            today -= timedelta(days=1)
        self.today = today

        self.shift = Shift.objects.create(
            name="Morning", code="INT-MORNING", start_time=datetime_time(9, 0), end_time=datetime_time(18, 0),
            is_active=True,
        )
        self.employee_user = User.objects.create_user(
            email="intelligence-employee@example.test", first_name="Asha", last_name="Rao",
        )
        self.employee = Employee.objects.create(
            user=self.employee_user, department="Engineering", employment_type="PERMANENT",
            date_joined=self.today - timedelta(days=30), section="C", subsection="C1",
            shift=self.shift,
        )
        self.other_user = User.objects.create_user(
            email="out-of-scope@example.test", first_name="Out", last_name="Scope",
        )
        self.other = Employee.objects.create(
            user=self.other_user, department="Marketing", employment_type="PERMANENT",
            date_joined=self.today - timedelta(days=30), section="D", subsection="D1",
        )
        self.scope = {"sections": ["C"], "subsections": ["C1"], "unrestricted": False}

    def event(self, employee, target_date, hour, event_type):
        timestamp = timezone.make_aware(datetime.combine(target_date, datetime.min.time()).replace(hour=hour))
        return AttendanceEvent.objects.create(employee=employee, timestamp=timestamp, event_type=event_type)

    def recompute(self, employee, target_date):
        attendance, _ = Attendance.objects.get_or_create(employee=employee, date=target_date)
        attendance.recompute_from_events()
        return attendance

    def test_missing_checkins_and_scope(self):
        result = attendance_intelligence.missing_checkins(user=self.admin, scope=self.scope, target_date=self.today)
        self.assertEqual(result["metric"], "missing_checkins")
        self.assertEqual(result["date_range"]["start"], self.today.isoformat())
        self.assertEqual([row["employee_id"] for row in result["rows"]], [self.employee.id])
        self.event(self.employee, self.today, 9, "CHECK_IN")
        self.recompute(self.employee, self.today)
        result = attendance_intelligence.missing_checkins(user=self.admin, scope=self.scope, target_date=self.today)
        self.assertEqual(result["rows"], [])
        self.assertNotIn(self.other.id, {row["employee_id"] for row in result["rows"]})

    def test_late_employees_reuses_shift_adherence(self):
        self.event(self.employee, self.today, 10, "CHECK_IN")
        self.recompute(self.employee, self.today)
        result = attendance_intelligence.late_employees(user=self.admin, scope=self.scope, target_date=self.today)
        self.assertEqual([row["employee_id"] for row in result["rows"]], [self.employee.id])

    def test_working_hours_uses_effective_closed_intervals(self):
        target = self.today - timedelta(days=1)
        self.event(self.employee, target, 9, "CHECK_IN")
        self.event(self.employee, target, 13, "CHECK_OUT")
        self.event(self.employee, target, 14, "CHECK_IN")
        self.event(self.employee, target, 18, "CHECK_OUT")
        self.recompute(self.employee, target)
        result = attendance_intelligence.working_hours(
            scope=self.scope, start=target, end=target, user=self.admin, target_employee_id=self.employee.id,
        )
        self.assertEqual(result["rows"][0]["total_working_seconds"], 8 * 60 * 60)
        self.assertTrue(any("closed" in item for item in result["assumptions"]))

    def test_incomplete_explanation_uses_effective_open_event(self):
        self.event(self.employee, self.today, 9, "CHECK_IN")
        self.recompute(self.employee, self.today)
        result = attendance_intelligence.incomplete_explanation(
            scope=self.scope, target_date=self.today, user=self.admin, target_employee_id=self.employee.id,
        )
        self.assertTrue(result["rows"][0]["needs_regularization"])
        self.assertIn("without a following check-out", result["rows"][0]["explanation"])

    def test_absence_streaks_summary_and_week_comparison(self):
        end = self.today - timedelta(days=1)
        start = end - timedelta(days=6)
        streaks = attendance_intelligence.absence_streaks(user=self.admin, scope=self.scope, start=start, end=end)
        self.assertEqual(streaks["rows"][0]["employee_id"], self.employee.id)
        summary = attendance_intelligence.summary(user=self.admin, scope=self.scope, start=start, end=end)
        self.assertTrue(summary["rows"])
        comparison = attendance_intelligence.period_comparison(user=self.admin, scope=self.scope, end_date=self.today)
        self.assertIn("current", comparison["date_range"])
        self.assertIn("delta", comparison["rows"][0])

    def test_semantic_layer_uses_one_metric_intent_for_natural_variation(self):
        with patch("hr_copilot.services.semantic_interpreter.get_structured_intent", return_value={
            "intent": "attendance_intelligence",
            "entities": {"attendance_metric": "late_employees", "temporal_expression": "today"},
        }):
            intent = analyze_question("Which staff arrived after the shift start today?")
        self.assertEqual(intent["intent"], "attendance_intelligence")
        self.assertEqual(intent["entities"]["attendance_metric"], "late_employees")
        self.assertEqual(intent["entities"]["date_range"]["start"], timezone.localdate().isoformat())
