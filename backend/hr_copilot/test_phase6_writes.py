from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from attendance.models import Attendance, AttendanceEvent, RegularizationRequest, Shift, get_effective_attendance_events
from employees.models import Employee
from hr_copilot.services.pipeline import CopilotError
from hr_copilot.services.write_actions import write_action_planner
from hr_copilot.services.write_executor import pending_action_manager, write_action_executor
from leave_management.models import LeavePolicy, LeaveRequest, LeaveType


class Phase6WriteTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email="phase6-admin@example.test", is_system_admin=True,
            hr_copilot_sections=["C"], hr_copilot_subsections=["C1"],
        )
        user = User.objects.create_user(email="phase6-employee@example.test", first_name="Asha", last_name="Rao")
        self.employee = Employee.objects.create(
            user=user, department="Engineering", employment_type="PERMANENT",
            date_joined=timezone.localdate() - timedelta(days=60), section="C", subsection="C1",
        )
        self.scope = {"sections": ["C"], "subsections": ["C1"], "unrestricted": False}
        self.shift = Shift.objects.create(name="Morning", code="PHASE6-MORNING", start_time=time(9), end_time=time(18), employment_type="PERMANENT")
        self.leave_type = LeaveType.objects.create(name="Annual", code="PHASE6-ANNUAL", is_active=True)
        LeavePolicy.objects.create(
            employee_type="PERMANENT", leave_type=self.leave_type, annual_entitlement=Decimal("20"),
            effective_from=timezone.localdate().replace(month=1, day=1), is_active=True,
        )

    def intent(self, name, entities):
        return {"intent": name, "source": "attendance" if "regularization" in name or "attendance" in name else "employee", "entities": entities, "action_type": "write", "requires_approval": True}

    def execute(self, intent):
        session = f"hr-copilot-user-{self.admin.id}-phase6"
        pending = write_action_planner.plan_write_action(intent, self.admin, session)
        self.assertTrue(pending["requires_confirmation"])
        action_id = pending_action_manager.store_pending_action(session, pending)
        approved = pending_action_manager.approve_action(session, action_id, self.admin.id)
        result = write_action_executor.execute_approved_action(approved, self.admin)
        pending_action_manager.mark_executed(action_id, self.admin.id, session, result)
        return result

    def test_attendance_edit_preserves_historical_events(self):
        target = timezone.localdate() - timedelta(days=3)
        original = timezone.make_aware(datetime.combine(target, time(8, 30)))
        AttendanceEvent.objects.create(employee=self.employee, timestamp=original, event_type="CHECK_IN")
        Attendance.objects.create(employee=self.employee, date=target, status="INCOMPLETE")
        result = self.execute(self.intent("attendance_update", {
            "employee_id": self.employee.id, "date_range": {"start": target.isoformat(), "end": target.isoformat()},
            "target_status": "PRESENT", "check_in_time": "09:00", "check_out_time": "18:00",
        }))
        self.assertEqual(result["status"], "PRESENT")
        self.assertTrue(AttendanceEvent.objects.filter(employee=self.employee, timestamp=original).exists())
        self.assertTrue(AttendanceEvent.objects.filter(employee=self.employee, correction__isnull=False).exists())

    def test_force_checkout_creates_admin_event(self):
        target = timezone.localdate()
        Attendance.objects.create(employee=self.employee, date=target, status="INCOMPLETE")
        AttendanceEvent.objects.create(employee=self.employee, shift=self.shift, timestamp=timezone.make_aware(datetime.combine(target, time(9))), event_type="CHECK_IN")
        result = self.execute(self.intent("attendance_force_checkout", {
            "employee_id": self.employee.id, "date_range": {"start": target.isoformat(), "end": target.isoformat()},
        }))
        self.assertEqual(result["operation"], "force_checkout")
        self.assertTrue(AttendanceEvent.objects.filter(employee=self.employee, timestamp__date=target, event_type="CHECK_OUT", source="ADMIN").exists())

    def test_leave_create_uses_exact_leave_type_and_service_rules(self):
        target = timezone.localdate() + timedelta(days=5)
        result = self.execute(self.intent("leave_create", {
            "employee_id": self.employee.id, "date_range": {"start": target.isoformat(), "end": target.isoformat()},
            "duration_days": 1, "reason": "Personal appointment", "leave_type": self.leave_type.code,
        }))
        request = LeaveRequest.objects.get(pk=result["leave_request_id"])
        self.assertEqual(request.leave_type_id, self.leave_type.id)
        self.assertEqual(request.status, "PENDING")

    def test_regularization_approve_preserves_correction_integrity(self):
        target = timezone.localdate() - timedelta(days=1)
        request = RegularizationRequest.objects.create(
            employee=self.employee, attendance_date=target, request_type="FORGOT_CHECK_OUT",
            requested_check_in=timezone.make_aware(datetime.combine(target, time(9))), reason="Forgot checkout",
        )
        result = self.execute(self.intent("regularization_approve", {"request_id": request.id, "employee_id": self.employee.id}))
        request.refresh_from_db()
        self.assertEqual(result["status"], "APPROVED")
        self.assertEqual(request.status, "APPROVED")
        self.assertIsNotNone(request.attendance_correction_id)
        self.assertTrue(AttendanceEvent.objects.filter(correction_id=request.attendance_correction_id).exists())

    def test_shift_assignment_and_permission_isolation(self):
        result = self.execute(self.intent("employee_shift_assign", {
            "employee_id": self.employee.id, "shift_id": self.shift.id,
        }))
        self.employee.refresh_from_db()
        self.assertEqual(result["shift_id"], self.shift.id)
        self.assertEqual(self.employee.shift_id, self.shift.id)
        outside_user = get_user_model().objects.create_user(email="phase6-outside@example.test")
        outside = Employee.objects.create(user=outside_user, department="Finance", employment_type="PERMANENT", date_joined=timezone.localdate(), section="D", subsection="D1")
        with self.assertRaises(CopilotError) as error:
            write_action_planner.plan_write_action(self.intent("employee_shift_assign", {"employee_id": outside.id, "shift_id": self.shift.id}), self.admin, "phase6-denied")
        self.assertEqual(error.exception.code, "scope_denied")

    def test_employee_deactivation_requires_confirmation_and_updates_account(self):
        result = self.execute(self.intent("employee_status_update", {
            "employee_id": self.employee.id, "is_active": False,
        }))
        self.employee.refresh_from_db()
        self.assertEqual(result["operation"], "deactivated")
        self.assertFalse(self.employee.is_active)

    def test_ambiguous_leave_cancel_and_repeated_confirmation_are_rejected(self):
        target = timezone.localdate() + timedelta(days=5)
        for offset in (0, 2):
            LeaveRequest.objects.create(employee=self.employee, leave_type=self.leave_type, start_date=target + timedelta(days=offset), end_date=target + timedelta(days=offset), duration_days=Decimal("1"), reason="Holiday", status="PENDING")
        with self.assertRaises(CopilotError) as error:
            write_action_planner.plan_write_action(self.intent("leave_cancel", {"employee_id": self.employee.id}), self.admin, "phase6-ambiguous")
        self.assertEqual(error.exception.code, "leave_request_ambiguous")

        pending = write_action_planner.plan_write_action(self.intent("employee_shift_assign", {"employee_id": self.employee.id, "shift_id": self.shift.id}), self.admin, "phase6-idempotent")
        action_id = pending_action_manager.store_pending_action("phase6-idempotent", pending)
        pending_action_manager.approve_action("phase6-idempotent", action_id, self.admin.id)
        with self.assertRaises(CopilotError):
            pending_action_manager.approve_action("phase6-idempotent", action_id, self.admin.id)
