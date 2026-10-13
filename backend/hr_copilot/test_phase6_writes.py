from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.models import ManagerScope
from attendance.models import (Attendance, AttendanceEvent,
                               RegularizationRequest, Shift,
                               get_effective_attendance_events)
from employees.models import Employee
from hr_copilot.services.pipeline import CopilotError
from hr_copilot.services.write_actions import write_action_planner
from hr_copilot.services.write_executor import (pending_action_manager,
                                                write_action_executor)
from leave_management.models import LeavePolicy, LeaveRequest, LeaveType


class Phase6WriteTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email="phase6-admin@example.test",
            is_system_admin=True,
        )
        ManagerScope.objects.create(
            manager=self.admin, scope_type="SECTION", value="C"
        )
        ManagerScope.objects.create(
            manager=self.admin, scope_type="DEPARTMENT", value="Engineering"
        )

        user = User.objects.create_user(
            email="phase6-employee@example.test",
            first_name="Asha",
            last_name="Rao",
        )
        self.employee = Employee.objects.create(
            user=user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined=timezone.localdate() - timedelta(days=60),
            section="C",
            subsection="C1",
        )
        self.scope = {
            "sections": ["C"],
            "subsections": ["C1"],
            "unrestricted": False,
        }
        self.shift = Shift.objects.create(
            name="Morning",
            code="PHASE6-MORNING",
            start_time=time(9),
            end_time=time(18),
            employment_type="PERMANENT",
        )
        self.leave_type = LeaveType.objects.create(
            name="Annual", code="PHASE6-ANNUAL", is_active=True
        )
        LeavePolicy.objects.create(
            employee_type="PERMANENT",
            leave_type=self.leave_type,
            annual_entitlement=Decimal("20"),
            effective_from=timezone.localdate().replace(month=1, day=1),
            is_active=True,
        )

    def intent(self, name, entities):
        return {
            "intent": name,
            "source": "attendance"
            if "regularization" in name or "attendance" in name
            else "employee",
            "entities": entities,
            "action_type": "write",
            "requires_approval": True,
        }

    def execute(self, intent):
        session = f"hr-copilot-user-{self.admin.id}-phase6"
        session = "attendance-create-stale-confirmation"
        pending = write_action_planner.plan_write_action(
            intent, self.admin, session
        )
        self.assertTrue(pending["requires_confirmation"])
        action_id = pending_action_manager.store_pending_action(
            session, pending
        )
        approved = pending_action_manager.approve_action(
            session, action_id, self.admin.id
        )
        result = write_action_executor.execute_approved_action(
            approved, self.admin
        )
        pending_action_manager.mark_executed(
            action_id, self.admin.id, session, result
        )
        return result

    def test_attendance_edit_preserves_historical_events(self):
        target = timezone.localdate()
        original = timezone.make_aware(datetime.combine(target, time(8, 30)))
        AttendanceEvent.objects.create(
            employee=self.employee, timestamp=original, event_type="CHECK_IN"
        )
        Attendance.objects.create(
            employee=self.employee, date=target, status="INCOMPLETE"
        )
        result = self.execute(
            self.intent(
                "attendance_update",
                {
                    "employee_id": self.employee.id,
                    "date_range": {
                        "start": target.isoformat(),
                        "end": target.isoformat(),
                    },
                    "target_status": "PRESENT",
                    "check_in_time": "09:00",
                    "check_out_time": "18:00",
                },
            )
        )
        self.assertEqual(result["status"], "PRESENT")
        self.assertTrue(
            AttendanceEvent.objects.filter(
                employee=self.employee, timestamp=original
            ).exists()
        )
        self.assertTrue(
            AttendanceEvent.objects.filter(
                employee=self.employee, correction__isnull=False
            ).exists()
        )

    def test_attendance_update_creates_missing_record_and_audited_events(self):
        target = timezone.localdate()
        intent = self.intent(
            "attendance_update",
            {
                "employee_id": self.employee.id,
                "date_range": {"start": target.isoformat(), "end": target.isoformat()},
                "target_status": "PRESENT",
                "check_in_time": "09:00",
                "check_out_time": "18:00",
            },
        )

        pending = write_action_planner.plan_write_action(
            intent, self.admin, "phase6-attendance-create"
        )

        self.assertEqual(pending["action_type"], "attendance_update")
        self.assertFalse(pending["current_state"]["exists"])
        result = self.execute(intent)
        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "created")
        self.assertEqual(result["status"], "PRESENT")
        self.assertTrue(
            Attendance.objects.filter(employee=self.employee, date=target).exists()
        )
        events = AttendanceEvent.objects.filter(
            employee=self.employee, timestamp__date=target
        )
        self.assertEqual(events.count(), 2)
        self.assertEqual(
            set(events.values_list("event_type", flat=True)),
            {"CHECK_IN", "CHECK_OUT"},
        )

    def test_attendance_create_uses_confirmed_create_execution_path(self):
        target = timezone.localdate()
        intent = self.intent(
            "attendance_create",
            {
                "employee_id": self.employee.id,
                "date_range": {"start": target.isoformat(), "end": target.isoformat()},
                "target_status": "PRESENT",
                "check_in_time": "09:00",
                "check_out_time": "18:00",
            },
        )
        session = f"hr-copilot-user-{self.admin.id}-attendance-create"
        pending = write_action_planner.plan_write_action(intent, self.admin, session)

        self.assertEqual(pending["action_type"], "attendance_create")
        self.assertTrue(pending["requires_confirmation"])
        self.assertFalse(pending["current_state"]["exists"])
        action_id = pending_action_manager.store_pending_action(session, pending)
        approved = pending_action_manager.approve_action(session, action_id, self.admin.id)
        result = write_action_executor.execute_approved_action(approved, self.admin)
        pending_action_manager.mark_executed(action_id, self.admin.id, session, result)

        self.assertTrue(result["success"])
        self.assertEqual(result["operation"], "created")
        self.assertEqual(result["status"], "PRESENT")
        self.assertEqual(
            set(AttendanceEvent.objects.filter(
                employee=self.employee, timestamp__date=target
            ).values_list("event_type", flat=True)),
            {"CHECK_IN", "CHECK_OUT"},
        )
        self.assertTrue(AttendanceEvent.objects.filter(
            employee=self.employee, timestamp__date=target,
            correction__isnull=False,
        ).exists())

    def test_attendance_create_rejects_duplicate_and_out_of_scope_employee(self):
        target = timezone.localdate()
        Attendance.objects.create(employee=self.employee, date=target, status="ABSENT")
        duplicate = self.intent(
            "attendance_create",
            {"employee_id": self.employee.id,
             "date_range": {"start": target.isoformat(), "end": target.isoformat()},
             "target_status": "PRESENT", "check_in_time": "09:00", "check_out_time": "18:00"},
        )
        with self.assertRaises(CopilotError) as error:
            write_action_planner.plan_write_action(duplicate, self.admin, "duplicate-create")
        self.assertEqual(error.exception.code, "attendance_exists")

        outside_user = get_user_model().objects.create_user(
            email="phase6-outside-create@example.test"
        )
        outside = Employee.objects.create(
            user=outside_user,
            department="Finance",
            employment_type="PERMANENT",
            date_joined=target - timedelta(days=10),
            section="D",
            subsection="D1",
        )
        unauthorized = self.intent(
            "attendance_create",
            {"employee_id": outside.id,
             "date_range": {"start": target.isoformat(), "end": target.isoformat()},
             "target_status": "ABSENT"},
        )
        with self.assertRaises(CopilotError) as error:
            write_action_planner.plan_write_action(unauthorized, self.admin, "outside-create")
        self.assertEqual(error.exception.code, "scope_denied")
        self.assertEqual(error.exception.status, 403)

    def test_attendance_create_rechecks_duplicates_after_confirmation(self):
        target = timezone.localdate()
        pending = write_action_planner.plan_write_action(
            self.intent(
                "attendance_create",
                {"employee_id": self.employee.id,
                 "date_range": {"start": target.isoformat(), "end": target.isoformat()},
                 "target_status": "ABSENT"},
            ),
            self.admin,
            session,
        )
        action_id = pending_action_manager.store_pending_action(session, pending)
        approved = pending_action_manager.approve_action(
            session, action_id, self.admin.id
        )
        Attendance.objects.create(employee=self.employee, date=target, status="PRESENT")

        with self.assertRaises(CopilotError) as error:
            write_action_executor.execute_approved_action(approved, self.admin)

        self.assertEqual(error.exception.code, "attendance_exists")
        self.assertEqual(
            Attendance.objects.get(employee=self.employee, date=target).status,
            "PRESENT",
        )

    def test_attendance_update_outside_manager_scope_is_rejected(self):
        outside_user = get_user_model().objects.create_user(
            email="phase6-outside-attendance@example.test"
        )
        outside = Employee.objects.create(
            user=outside_user,
            department="Finance",
            employment_type="PERMANENT",
            date_joined=timezone.localdate(),
            section="D",
            subsection="D1",
        )
        target = timezone.localdate()

        with self.assertRaises(CopilotError) as error:
            write_action_planner.plan_write_action(
                self.intent(
                    "attendance_update",
                    {
                        "employee_id": outside.id,
                        "date_range": {
                            "start": target.isoformat(),
                            "end": target.isoformat(),
                        },
                        "target_status": "ABSENT",
                    },
                ),
                self.admin,
                "phase6-attendance-scope-denied",
            )

        self.assertEqual(error.exception.code, "scope_denied")

    def test_present_attendance_plan_requests_missing_times(self):
        target = timezone.localdate()
        pending = write_action_planner.plan_write_action(
            self.intent(
                "attendance_update",
                {
                    "employee_id": self.employee.id,
                    "date_range": {
                        "start": target.isoformat(),
                        "end": target.isoformat(),
                    },
                    "target_status": "PRESENT",
                },
            ),
            self.admin,
            "phase6-attendance-missing-times",
        )

        self.assertFalse(pending["validated"])
        self.assertEqual(
            pending["validation_errors"], ["check_in_time", "check_out_time"]
        )
        self.assertTrue(pending["requires_confirmation"])

    def test_leave_plan_requires_reason_before_execution(self):
        target = timezone.localdate() + timedelta(days=5)
        pending = write_action_planner.plan_write_action(
            self.intent(
                "leave_create",
                {
                    "employee_id": self.employee.id,
                    "date_range": {
                        "start": target.isoformat(),
                        "end": target.isoformat(),
                    },
                    "leave_type": self.leave_type.code,
                },
            ),
            self.admin,
            "phase6-leave-missing-reason",
        )

        self.assertEqual(pending["status"], "AWAITING_INFORMATION")
        self.assertFalse(pending["validated"])
        self.assertEqual(pending["validation_errors"], ["reason"])

    def test_leave_plan_rejects_ambiguous_name_or_code(self):
        LeaveType.objects.create(
            name=self.leave_type.code,
            code="PHASE6-ALTERNATE",
            is_active=True,
        )
        target = timezone.localdate() + timedelta(days=5)

        with self.assertRaises(CopilotError) as error:
            write_action_planner.plan_write_action(
                self.intent(
                    "leave_create",
                    {
                        "employee_id": self.employee.id,
                        "date_range": {
                            "start": target.isoformat(),
                            "end": target.isoformat(),
                        },
                        "leave_type": self.leave_type.code,
                    },
                ),
                self.admin,
                "phase6-leave-type-ambiguous",
            )

        self.assertEqual(error.exception.code, "leave_type_ambiguous")

    def test_force_checkout_creates_admin_event(self):
        target = timezone.localdate()
        Attendance.objects.create(
            employee=self.employee, date=target, status="INCOMPLETE"
        )
        AttendanceEvent.objects.create(
            employee=self.employee,
            shift=self.shift,
            timestamp=timezone.make_aware(datetime.combine(target, time(9))),
            event_type="CHECK_IN",
        )
        result = self.execute(
            self.intent(
                "attendance_force_checkout",
                {
                    "employee_id": self.employee.id,
                    "date_range": {
                        "start": target.isoformat(),
                        "end": target.isoformat(),
                    },
                },
            )
        )
        self.assertEqual(result["operation"], "force_checkout")
        self.assertTrue(
            AttendanceEvent.objects.filter(
                employee=self.employee,
                timestamp__date=target,
                event_type="CHECK_OUT",
                source="ADMIN",
            ).exists()
        )

    def test_leave_create_uses_exact_leave_type_and_service_rules(self):
        target = timezone.localdate() + timedelta(days=1)
        while target.weekday() >= 5:
            target += timedelta(days=1)
        result = self.execute(
            self.intent(
                "leave_create",
                {
                    "employee_id": self.employee.id,
                    "date_range": {
                        "start": target.isoformat(),
                        "end": target.isoformat(),
                    },
                    "duration_days": 1,
                    "reason": "Personal appointment",
                    "leave_type": self.leave_type.code,
                },
            )
        )
        request = LeaveRequest.objects.get(pk=result["leave_request_id"])
        self.assertEqual(request.leave_type_id, self.leave_type.id)
        self.assertEqual(request.status, "PENDING")

    def test_regularization_approve_preserves_correction_integrity(self):
        target = timezone.localdate() - timedelta(days=1)
        request = RegularizationRequest.objects.create(
            employee=self.employee,
            attendance_date=target,
            request_type="FORGOT_CHECK_OUT",
            requested_check_in=timezone.make_aware(
                datetime.combine(target, time(9))
            ),
            reason="Forgot checkout",
        )
        result = self.execute(
            self.intent(
                "regularization_approve",
                {"request_id": request.id, "employee_id": self.employee.id},
            )
        )
        request.refresh_from_db()
        self.assertEqual(result["status"], "APPROVED")
        self.assertEqual(request.status, "APPROVED")
        self.assertIsNotNone(request.attendance_correction_id)
        self.assertTrue(
            AttendanceEvent.objects.filter(
                correction_id=request.attendance_correction_id
            ).exists()
        )

    def test_shift_assignment_and_permission_isolation(self):
        result = self.execute(
            self.intent(
                "employee_shift_assign",
                {
                    "employee_id": self.employee.id,
                    "shift_id": self.shift.id,
                },
            )
        )
        self.employee.refresh_from_db()
        self.assertEqual(result["shift_id"], self.shift.id)
        self.assertEqual(self.employee.shift_id, self.shift.id)
        outside_user = get_user_model().objects.create_user(
            email="phase6-outside@example.test"
        )
        outside = Employee.objects.create(
            user=outside_user,
            department="Finance",
            employment_type="PERMANENT",
            date_joined=timezone.localdate(),
            section="D",
            subsection="D1",
        )
        with self.assertRaises(CopilotError) as error:
            write_action_planner.plan_write_action(
                self.intent(
                    "employee_shift_assign",
                    {"employee_id": outside.id, "shift_id": self.shift.id},
                ),
                self.admin,
                "phase6-denied",
            )
        self.assertEqual(error.exception.code, "scope_denied")

    def test_employee_deactivation_requires_confirmation_and_updates_account(
        self,
    ):
        result = self.execute(
            self.intent(
                "employee_status_update",
                {
                    "employee_id": self.employee.id,
                    "is_active": False,
                },
            )
        )
        self.employee.refresh_from_db()
        self.assertEqual(result["operation"], "deactivated")
        self.assertFalse(self.employee.is_active)

    def test_ambiguous_leave_cancel_and_repeated_confirmation_are_rejected(
        self,
    ):
        target = timezone.localdate() + timedelta(days=5)
        for offset in (0, 2):
            LeaveRequest.objects.create(
                employee=self.employee,
                leave_type=self.leave_type,
                start_date=target + timedelta(days=offset),
                end_date=target + timedelta(days=offset),
                duration_days=Decimal("1"),
                reason="Holiday",
                status="PENDING",
            )
        with self.assertRaises(CopilotError) as error:
            write_action_planner.plan_write_action(
                self.intent("leave_cancel", {"employee_id": self.employee.id}),
                self.admin,
                "phase6-ambiguous",
            )
        self.assertEqual(error.exception.code, "leave_request_ambiguous")

        pending = write_action_planner.plan_write_action(
            self.intent(
                "employee_shift_assign",
                {"employee_id": self.employee.id, "shift_id": self.shift.id},
            ),
            self.admin,
            "phase6-idempotent",
        )
        action_id = pending_action_manager.store_pending_action(
            "phase6-idempotent", pending
        )
        pending_action_manager.approve_action(
            "phase6-idempotent", action_id, self.admin.id
        )
        with self.assertRaises(CopilotError):
            pending_action_manager.approve_action(
                "phase6-idempotent", action_id, self.admin.id
            )

    def test_attendance_planner_rejects_invalid_status_and_inverted_times(self):
        target = timezone.localdate()
        base = {
            "employee_id": self.employee.id,
            "date_range": {
                "start": target.isoformat(),
                "end": target.isoformat(),
            },
        }

        for entities, expected_code in (
            ({**base, "target_status": "UNKNOWN"}, "invalid_status"),
            (
                {
                    **base,
                    "target_status": "PRESENT",
                    "check_in_time": "18:00",
                    "check_out_time": "09:00",
                },
                "invalid_attendance_time",
            ),
        ):
            with self.subTest(expected_code=expected_code):
                with self.assertRaises(CopilotError) as error:
                    write_action_planner.plan_write_action(
                        self.intent("attendance_update", entities),
                        self.admin,
                        f"phase6-invalid-attendance-{expected_code}",
                    )
                self.assertEqual(error.exception.code, expected_code)

    def test_attendance_planner_requires_admin_for_past_changes(self):
        target = timezone.localdate() - timedelta(days=1)
        intent = self.intent(
            "attendance_update",
            {
                "employee_id": self.employee.id,
                "date_range": {
                    "start": target.isoformat(),
                    "end": target.isoformat(),
                },
                "target_status": "ABSENT",
            },
        )
        manager = get_user_model().objects.create_user(
            email="phase6-past-attendance-manager@example.test",
            is_system_admin=True,
        )
        ManagerScope.objects.create(
            manager=manager, scope_type="DEPARTMENT", value="Engineering"
        )

        with self.assertRaises(CopilotError) as error:
            write_action_planner.plan_write_action(
                intent, manager, "phase6-past-attendance-denied"
            )

        self.assertEqual(error.exception.code, "admin_only")
        self.assertEqual(error.exception.status, 403)

    def test_force_checkout_requires_latest_attendance_event_to_be_check_in(
        self,
    ):
        target = timezone.localdate()
        AttendanceEvent.objects.create(
            employee=self.employee,
            shift=self.shift,
            timestamp=timezone.make_aware(datetime.combine(target, time(9))),
            event_type="CHECK_IN",
        )
        AttendanceEvent.objects.create(
            employee=self.employee,
            shift=self.shift,
            timestamp=timezone.make_aware(datetime.combine(target, time(12))),
            event_type="CHECK_OUT",
        )

        with self.assertRaises(CopilotError) as error:
            write_action_planner.plan_write_action(
                self.intent(
                    "attendance_force_checkout",
                    {
                        "employee_id": self.employee.id,
                        "date_range": {
                            "start": target.isoformat(),
                            "end": target.isoformat(),
                        },
                    },
                ),
                self.admin,
                "phase6-force-checkout-closed",
            )

        self.assertEqual(error.exception.code, "no_active_checkin")

    def test_leave_review_requires_scoped_pending_request_and_denial_reason(
        self,
    ):
        target = timezone.localdate() + timedelta(days=5)
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=target,
            end_date=target,
            duration_days=Decimal(1),
            reason="Personal appointment",
            status="PENDING",
        )
        entities = {
            "employee_id": self.employee.id,
            "request_id": leave.id,
        }

        with self.assertRaises(CopilotError) as error:
            write_action_planner.plan_write_action(
                self.intent("leave_deny", entities),
                self.admin,
                "phase6-denial-reason-required",
            )
        self.assertEqual(error.exception.code, "review_reason_required")

        pending = write_action_planner.plan_write_action(
            self.intent("leave_approve", entities),
            self.admin,
            "phase6-leave-review-approved-preview",
        )
        self.assertEqual(pending["proposed_changes"]["status"], "APPROVED")
        self.assertTrue(pending["requires_confirmation"])
        self.assertEqual(pending["target_data"]["leave_request_id"], leave.id)

    def test_regularization_planning_validates_times_and_review_scope(self):
        target = timezone.localdate() - timedelta(days=1)
        create = self.intent(
            "regularization_create",
            {
                "employee_id": self.employee.id,
                "date_range": {
                    "start": target.isoformat(),
                    "end": target.isoformat(),
                },
                "request_type": "FORGOT_CHECK_IN",
                "reason": "Forgot to check in",
                "check_in_time": "not-a-time",
            },
        )

        with self.assertRaises(CopilotError) as error:
            write_action_planner.plan_write_action(
                create, self.admin, "phase6-regularization-invalid-time"
            )
        self.assertEqual(error.exception.code, "invalid_regularization_time")

        request = RegularizationRequest.objects.create(
            employee=self.employee,
            attendance_date=target,
            request_type="FORGOT_CHECK_IN",
            reason="Forgot to check in",
        )
        reject = self.intent(
            "regularization_reject",
            {"request_id": request.id, "reason": "No supporting details"},
        )
        pending = write_action_planner.plan_write_action(
            reject, self.admin, "phase6-regularization-reject-preview"
        )
        self.assertEqual(pending["proposed_changes"]["status"], "REJECTED")
        self.assertEqual(
            pending["proposed_changes"]["reason"], "No supporting details"
        )
        self.assertTrue(pending["requires_confirmation"])

    def test_regularization_create_persists_both_requested_times(self):
        target = timezone.localdate() - timedelta(days=1)
        intent = self.intent(
            "regularization_create",
            {
                "employee_id": self.employee.id,
                "date_range": {"start": target.isoformat(), "end": target.isoformat()},
                "request_type": "INCORRECT_ATTENDANCE",
                "reason": "Forgot to record both events",
                "check_in_time": "09:05",
                "check_out_time": "18:10",
            },
        )

        result = self.execute(intent)
        request = RegularizationRequest.objects.get(pk=result["request_id"])

        self.assertEqual(request.status, "PENDING")
        self.assertEqual(request.attendance_date, target)
        self.assertEqual(
            timezone.localtime(request.requested_check_in).time(), time(9, 5)
        )
        self.assertEqual(
            timezone.localtime(request.requested_check_out).time(), time(18, 10)
        )

    def test_shift_planning_rejects_incompatible_employment_type(self):
        intern_shift = Shift.objects.create(
            name="Intern Shift",
            code="PHASE6-INTERN",
            start_time=time(10),
            end_time=time(17),
            employment_type="INTERN",
        )

        with self.assertRaises(CopilotError) as error:
            write_action_planner.plan_write_action(
                self.intent(
                    "employee_shift_assign",
                    {
                        "employee_id": self.employee.id,
                        "shift_id": intern_shift.id,
                    },
                ),
                self.admin,
                "phase6-incompatible-shift",
            )

        self.assertEqual(error.exception.code, "shift_incompatible")

    def test_target_employee_lookup_fails_closed_for_unknown_employee(self):
        with self.assertRaises(CopilotError) as error:
            write_action_planner.plan_write_action(
                self.intent(
                    "employee_status_update",
                    {"employee_id": 999999, "is_active": False},
                ),
                self.admin,
                "phase6-unknown-employee",
            )

        self.assertEqual(error.exception.code, "employee_not_found")

    def test_planner_rejects_read_intents_and_unimplemented_writes(self):
        with self.assertRaises(CopilotError) as read_error:
            write_action_planner.plan_write_action(
                {"intent": "employee_lookup", "action_type": "read"},
                self.admin,
                "phase6-read-is-not-write",
            )

        self.assertEqual(read_error.exception.code, "invalid_action")

        with self.assertRaises(CopilotError) as unsupported_error:
            write_action_planner.plan_write_action(
                {"intent": "future_write", "action_type": "write"},
                self.admin,
                "phase6-unsupported-write",
            )

        self.assertEqual(unsupported_error.exception.code, "unsupported_write")

    def test_attendance_planner_requires_date_and_status_before_confirmation(self):
        base = {
            "employee_id": self.employee.id,
            "date_range": {
                "start": timezone.localdate().isoformat(),
                "end": timezone.localdate().isoformat(),
            },
        }
        missing_date = self.intent(
            "attendance_update",
            {"employee_id": self.employee.id, "target_status": "ABSENT"},
        )
        missing_status = self.intent("attendance_update", base)

        for intent, expected_code in (
            (missing_date, "attendance_date_required"),
            (missing_status, "missing_status"),
        ):
            with self.subTest(expected_code=expected_code):
                with self.assertRaises(CopilotError) as error:
                    write_action_planner.plan_write_action(
                        intent, self.admin, f"phase6-required-{expected_code}"
                    )
                self.assertEqual(error.exception.code, expected_code)

    def test_attendance_status_inference_requests_times_before_confirmation(self):
        today = timezone.localdate().isoformat()
        intent = self.intent(
            "attendance_update",
            {
                "employee_id": self.employee.id,
                "date_range": {"start": today, "end": today},
            },
        )
        intent["original_query"] = "Mark Asha Rao present today"

        pending = write_action_planner.plan_write_action(
            intent, self.admin, "phase6-inferred-present"
        )

        self.assertEqual(pending["target_data"]["target_status"], "PRESENT")
        self.assertFalse(pending["validated"])
        self.assertEqual(
            pending["validation_errors"], ["check_in_time", "check_out_time"]
        )
        self.assertEqual(pending["status"], "AWAITING_INFORMATION")

    def test_attendance_status_fallbacks_use_the_original_request(self):
        target = timezone.localdate().isoformat()
        for phrase, expected_status in (
            ("Mark Asha Rao absent today", "ABSENT"),
            ("Mark Asha Rao incomplete today", "INCOMPLETE"),
            ("Put Asha Rao on leave today", "LEAVE"),
        ):
            with self.subTest(expected_status=expected_status):
                intent = self.intent(
                    "attendance_update",
                    {
                        "employee_id": self.employee.id,
                        "date_range": {"start": target, "end": target},
                        "reason": "Approved personal leave",
                    },
                )
                intent["original_query"] = phrase

                pending = write_action_planner.plan_write_action(
                    intent, self.admin, f"phase6-status-fallback-{expected_status}"
                )

                self.assertEqual(
                    pending["target_data"]["target_status"], expected_status
                )

    def test_leave_approval_failure_keeps_request_pending(self):
        target = timezone.localdate() + timedelta(days=1)
        while target.weekday() >= 5:
            target += timedelta(days=1)
        created = self.execute(
            self.intent(
                "leave_create",
                {
                    "employee_id": self.employee.id,
                    "date_range": {
                        "start": target.isoformat(),
                        "end": target.isoformat(),
                    },
                    "duration_days": 1,
                    "reason": "Personal appointment",
                    "leave_type": self.leave_type.code,
                },
            )
        )
        request = LeaveRequest.objects.get(pk=created["leave_request_id"])
        pending = write_action_planner.plan_write_action(
            self.intent(
                "leave_approve",
                {"employee_id": self.employee.id, "request_id": request.id},
            ),
            self.admin,
            "phase6-leave-approval-failure",
        )

        with patch(
            "leave_management.services.approve_leave_request",
            side_effect=RuntimeError("private service error"),
        ):
            with self.assertRaises(CopilotError) as error:
                write_action_executor.execute_approved_action(pending, self.admin)

        request.refresh_from_db()
        self.assertEqual(error.exception.code, "leave_review_failed")
        self.assertEqual(request.status, "PENDING")
        self.assertFalse(
            Attendance.objects.filter(employee=self.employee, date=target).exists()
        )

    @patch("holidays.services.attendance_required", return_value=False)
    @patch(
        "holidays.services.get_day_classification",
        return_value={"day_type": "WEEKEND"},
    )
    def test_attendance_planner_does_not_mark_non_required_day_absent(
        self, _day_classification, _attendance_required
    ):
        today = timezone.localdate().isoformat()
        intent = self.intent(
            "attendance_update",
            {
                "employee_id": self.employee.id,
                "date_range": {"start": today, "end": today},
                "target_status": "ABSENT",
            },
        )

        with self.assertRaises(CopilotError) as error:
            write_action_planner.plan_write_action(
                intent, self.admin, "phase6-absence-nonworking-day"
            )

        self.assertEqual(error.exception.code, "attendance_not_required")
        self.assertEqual(error.exception.status, 400)
