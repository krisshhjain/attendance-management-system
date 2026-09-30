"""Database integration tests for the HR Copilot read and approved-write paths.

Run with ``python manage.py test hr_copilot.test_database_operations``. Django
creates an isolated test database; these tests never write to development data.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from attendance.models import Attendance, AttendanceCorrection, AttendanceEvent, get_effective_attendance_events
from employees.models import Employee
from hr_copilot import views
from hr_copilot.models import CopilotPendingAction, CopilotActionAudit, CopilotConversationContext
from hr_copilot.services.intent_normalizer import IntentNormalizer
from hr_copilot.services.pipeline import CopilotError
from hr_copilot.services.semantic_interpreter import semantic_interpreter
from hr_copilot.services.write_actions import write_action_planner
from hr_copilot.services.write_executor import (
    PendingActionManager,
    pending_action_manager,
    write_action_executor,
)
from leave_management.models import LeaveRequest, LeaveType

# The regular pytest suite has no pytest-django database plugin. These tests
# are intentionally run by Django's test runner, which provisions a test DB.
__test__ = False


class HRCopilotDatabaseOperationTests(TransactionTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.admin = get_user_model().objects.create_user(
            email="copilot-admin@example.test",
            password="unused-test-password",
            first_name="Copilot",
            last_name="Admin",
            is_system_admin=True,
            hr_copilot_sections=["C"],
            hr_copilot_subsections=["C1"],
        )
        self.employee_user = get_user_model().objects.create_user(
            email="asha.rao@example.test",
            password="unused-test-password",
            first_name="Asha",
            last_name="Rao",
        )
        self.employee = Employee.objects.create(
            user=self.employee_user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined=date(2020, 1, 2),
            section="C",
            subsection="C1",
        )

    def _call_read_query(self, question, intent):
        request = self.factory.post(
            "/api/hr-copilot/query/",
            {"message": question},
            format="json",
        )
        force_authenticate(request, user=self.admin)
        with self.modify_analyze_intent(intent):
            return views.HRCopilotQueryView.as_view()(request)

    def modify_analyze_intent(self, intent):
        """Patch only NLP extraction; the query planner and test DB stay real."""
        from unittest.mock import patch

        return patch.object(views, "analyze_question", return_value=intent)

    def test_employee_count_reads_only_records_in_admin_scope(self):
        outside_user = get_user_model().objects.create_user(
            email="outside.scope@example.test", first_name="Outside", last_name="Scope",
        )
        Employee.objects.create(
            user=outside_user,
            department="Operations",
            employment_type="CONTRACT",
            date_joined=date(2022, 4, 5),
            section="D",
            subsection="D1",
        )
        intent = {
            "intent": "employee_count",
            "source": "employee",
            "entities": {},
            "action_type": "read",
            "requires_approval": False,
        }

        response = self._call_read_query("How many employees are in my scope?", intent)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["query_status"], "executed")
        self.assertEqual(response.data["data"]["rows"], [{"value": 1}])
        self.assertEqual(response.data["scope"], {"sections": ["C"], "subsections": ["C1"]})

    def test_attendance_read_returns_the_test_database_record(self):
        target_date = date.today() - timedelta(days=2)
        Attendance.objects.create(employee=self.employee, date=target_date, status="PRESENT")
        intent = {
            "intent": "attendance_lookup",
            "source": "attendance",
            "entities": {
                "employee_email": self.employee_user.email,
                "date_range": {"start": target_date.isoformat(), "end": target_date.isoformat()},
            },
            "action_type": "read",
            "requires_approval": False,
        }

        response = self._call_read_query("Show Asha Rao's attendance", intent)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["row_count"], 1)
        self.assertEqual(response.data["data"]["rows"][0]["status"], "PRESENT")
        self.assertEqual(response.data["data"]["rows"][0]["date"], target_date.isoformat())

    def test_leave_read_returns_the_test_database_request(self):
        start_date = date.today() + timedelta(days=6)
        leave_type = LeaveType.objects.create(name="Personal Leave", code="TEST-READ")
        LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=leave_type,
            start_date=start_date,
            end_date=start_date,
            duration_days=Decimal("1.0"),
            reason="Read integration test",
            status="PENDING",
        )
        intent = {
            "intent": "leave_lookup",
            "source": "leave",
            "entities": {
                "leave_status": "PENDING",
                "date_range": {"start": start_date.isoformat(), "end": start_date.isoformat()},
            },
            "action_type": "read",
            "requires_approval": False,
        }

        response = self._call_read_query("Show pending leave requests", intent)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["row_count"], 1)
        row = response.data["data"]["rows"][0]
        self.assertEqual(row["leave_type"], "Personal Leave")
        self.assertEqual(row["status"], "PENDING")
        self.assertEqual(row["reason"], "Read integration test")

    def _plan_and_approve(self, intent):
        session_id = f"hr-copilot-user-{self.admin.id}"
        pending_action = write_action_planner.plan_write_action(intent, self.admin, session_id)
        action_id = pending_action_manager.store_pending_action(session_id, pending_action)

        # A fresh manager instance sees the pending request from the database.
        persisted = PendingActionManager().get_pending_action(session_id, action_id, self.admin.id)
        self.assertEqual(str(persisted.action_id), action_id)
        self.assertEqual(persisted.status, "PENDING")

        approved = pending_action_manager.approve_action(session_id, action_id, self.admin.id)
        result = write_action_executor.execute_approved_action(approved, self.admin)
        pending_action_manager.mark_executed(action_id, self.admin.id, session_id, result)
        return action_id, result

    def test_approved_attendance_update_changes_the_database_record(self):
        target_date = date.today() - timedelta(days=3)
        attendance = Attendance.objects.create(
            employee=self.employee,
            date=target_date,
            status="INCOMPLETE",
        )
        intent = {
            "intent": "attendance_update",
            "source": "attendance",
            "action_type": "write",
            "requires_approval": True,
            "entities": {
                "employee_email": self.employee_user.email,
                "date_range": {"start": target_date.isoformat(), "end": target_date.isoformat()},
                "target_status": "PRESENT",
                "check_in_time": "09:00",
                "check_out_time": "18:00",
            },
        }

        action_id, result = self._plan_and_approve(intent)

        attendance.refresh_from_db()
        action = CopilotPendingAction.objects.get(action_id=action_id)
        self.assertEqual(attendance.status, "PRESENT")
        self.assertEqual(result["operation"], "updated")
        self.assertEqual(action.status, "EXECUTED")
        self.assertEqual(action.execution_result["status"], "PRESENT")
        audit = CopilotActionAudit.objects.get(pending_action=action)
        self.assertTrue(audit.success)
        self.assertTrue(audit.explicit_confirmation)

    def test_reported_mark_attendance_sentence_survives_name_to_id_resolution(self):
        target_user = get_user_model().objects.create_user(
            email="akshat.awasthi@example.test",
            first_name="Akshat",
            last_name="Awasthi",
        )
        target_employee = Employee.objects.create(
            user=target_user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined=date(2020, 1, 2),
            section="C",
            subsection="C1",
        )
        question = "Mark Akshat Awasthi attendance for 2026-09-28 as Present."
        normalized = IntentNormalizer().normalize_intent(
            {"intent": "attendance_update", "entities": {}},
            original_query=question,
        )
        interpreted = {"entities": normalized["entities"]}

        semantic_interpreter._detect_ambiguities(interpreted)
        self.assertEqual(interpreted["entities"].get("employee_id"), target_employee.id)
        self.assertNotIn("employee_name", interpreted["entities"])

        intent = {
            **normalized,
            "entities": interpreted["entities"],
            "original_query": question,
        }
        intent["entities"].update({"check_in_time": "09:00", "check_out_time": "18:00"})
        action_id, result = self._plan_and_approve(intent)

        attendance = Attendance.objects.get(employee=target_employee, date=date(2026, 9, 28))
        action = CopilotPendingAction.objects.get(action_id=action_id)
        self.assertEqual(attendance.status, "PRESENT")
        self.assertEqual(result["operation"], "created")
        self.assertEqual(action.status, "EXECUTED")

    def test_approved_attendance_create_inserts_a_database_record(self):
        target_date = date.today() - timedelta(days=4)
        intent = {
            "intent": "attendance_create",
            "source": "attendance",
            "action_type": "write",
            "requires_approval": True,
            "entities": {
                "employee_email": self.employee_user.email,
                "date_range": {"start": target_date.isoformat(), "end": target_date.isoformat()},
                "target_status": "PRESENT",
                "check_in_time": "09:00",
                "check_out_time": "18:00",
            },
        }

        action_id, result = self._plan_and_approve(intent)

        attendance = Attendance.objects.get(employee=self.employee, date=target_date)
        action = CopilotPendingAction.objects.get(action_id=action_id)
        self.assertEqual(attendance.status, "PRESENT")
        self.assertEqual(result["operation"], "created")
        self.assertEqual(action.status, "EXECUTED")

    def test_approved_leave_create_adds_pending_request(self):
        start_date = date.today() + timedelta(days=8)
        leave_type = LeaveType.objects.create(name="Annual Leave", code="TEST-CREATE")
        intent = {
            "intent": "leave_create",
            "source": "leave",
            "action_type": "write",
            "requires_approval": True,
            "entities": {
                "employee_email": self.employee_user.email,
                "date_range": {"start": start_date.isoformat(), "end": start_date.isoformat()},
                "duration_days": 1,
                "reason": "Integration test request",
            },
        }

        action_id, result = self._plan_and_approve(intent)

        leave_request = LeaveRequest.objects.get(id=result["leave_request_id"])
        action = CopilotPendingAction.objects.get(action_id=action_id)
        self.assertEqual(leave_request.employee, self.employee)
        self.assertEqual(leave_request.leave_type, leave_type)
        self.assertEqual(leave_request.status, "PENDING")
        self.assertEqual(leave_request.reason, "Integration test request")
        self.assertEqual(action.status, "EXECUTED")

    def test_approved_leave_cancel_updates_request_status(self):
        start_date = date.today() + timedelta(days=8)
        leave_type = LeaveType.objects.create(name="Annual Leave", code="TEST-CANCEL")
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=leave_type,
            start_date=start_date,
            end_date=start_date,
            duration_days=Decimal("1.0"),
            reason="Integration test request",
            status="PENDING",
        )
        intent = {
            "intent": "leave_cancel",
            "source": "leave",
            "action_type": "write",
            "requires_approval": True,
            "entities": {"employee_email": self.employee_user.email},
        }

        action_id, result = self._plan_and_approve(intent)

        leave_request.refresh_from_db()
        action = CopilotPendingAction.objects.get(action_id=action_id)
        self.assertEqual(leave_request.status, "CANCELLED")
        self.assertEqual(result["operation"], "cancelled")
        self.assertEqual(action.status, "EXECUTED")

    def test_approved_leave_review_updates_request_and_attendance(self):
        leave_date = date.today() + timedelta(days=1)
        while leave_date.weekday() >= 5:
            leave_date += timedelta(days=1)
        leave_type = LeaveType.objects.create(name="Annual Leave", code="TEST-ANNUAL")
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=leave_type,
            start_date=leave_date,
            end_date=leave_date,
            duration_days=Decimal("1.0"),
            reason="Integration test leave",
            status="PENDING",
        )
        intent = {
            "intent": "leave_approve",
            "source": "leave",
            "action_type": "write",
            "requires_approval": True,
            "entities": {
                "employee_email": self.employee_user.email,
                "date_range": {"start": leave_date.isoformat(), "end": leave_date.isoformat()},
            },
        }

        action_id, result = self._plan_and_approve(intent)

        leave_request.refresh_from_db()
        attendance = Attendance.objects.get(employee=self.employee, date=leave_date)
        action = CopilotPendingAction.objects.get(action_id=action_id)
        self.assertEqual(leave_request.status, "APPROVED")
        self.assertEqual(leave_request.reviewed_by, self.admin)
        self.assertEqual(attendance.status, "LEAVE")
        self.assertEqual(attendance.leave_request, leave_request)
        self.assertEqual(result["status"], "APPROVED")
        self.assertEqual(action.status, "EXECUTED")

    def test_denial_requires_reason_before_any_database_change(self):
        leave_date = date.today() + timedelta(days=7)
        leave_type = LeaveType.objects.create(name="Personal Leave", code="TEST-PERSONAL")
        leave_request = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=leave_type,
            start_date=leave_date,
            end_date=leave_date,
            duration_days=Decimal("1.0"),
            reason="Integration test leave",
            status="PENDING",
        )
        intent = {
            "intent": "leave_deny",
            "source": "leave",
            "action_type": "write",
            "requires_approval": True,
            "entities": {
                "employee_email": self.employee_user.email,
                "date_range": {"start": leave_date.isoformat(), "end": leave_date.isoformat()},
            },
        }

        with self.assertRaisesMessage(CopilotError, "Provide a reason for denying"):
            write_action_planner.plan_write_action(intent, self.admin, f"hr-copilot-user-{self.admin.id}")

        leave_request.refresh_from_db()
        self.assertEqual(leave_request.status, "PENDING")
        self.assertFalse(CopilotPendingAction.objects.exists())

        intent["entities"]["reason"] = "Insufficient staffing coverage"
        action_id, result = self._plan_and_approve(intent)

        leave_request.refresh_from_db()
        action = CopilotPendingAction.objects.get(action_id=action_id)
        self.assertEqual(leave_request.status, "DENIED")
        self.assertEqual(leave_request.reviewed_by, self.admin)
        self.assertEqual(leave_request.reviewer_remarks, "Insufficient staffing coverage")
        self.assertEqual(result["status"], "DENIED")
        self.assertEqual(action.status, "EXECUTED")

    def test_present_action_waits_for_both_times_and_followup_completes_same_action(self):
        target_date = date.today() - timedelta(days=1)
        intent = {
            "intent": "attendance_update", "source": "attendance", "action_type": "write",
            "requires_approval": True,
            "entities": {"employee_email": self.employee_user.email, "date_range": {"start": target_date.isoformat(), "end": target_date.isoformat()}, "target_status": "PRESENT"},
        }
        conversation_id = "test-conversation-followup"
        session_id = views.copilot_action_session_id(self.admin.id, conversation_id)
        draft = write_action_planner.plan_write_action(intent, self.admin, session_id)
        self.assertEqual(draft["status"], "AWAITING_INFORMATION")
        self.assertFalse(draft["validated"])
        self.assertEqual(draft["validation_errors"], ["check_in_time", "check_out_time"])
        draft["conversation_id"] = conversation_id
        action_id = pending_action_manager.store_pending_action(draft["session_id"], draft)

        request = self.factory.post("/api/hr-copilot/query/", {
            "message": "9:30 AM to 6 PM", "conversation_id": conversation_id,
        }, format="json")
        force_authenticate(request, user=self.admin)
        from unittest.mock import patch
        with patch.object(views, "extract_pending_action_fields", return_value={"check_in_time": "09:30", "check_out_time": "18:00"}):
            response = views.HRCopilotQueryView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["query_status"], "pending_approval")
        action = CopilotPendingAction.objects.get(action_id=action_id)
        self.assertEqual(action.status, "PENDING")
        self.assertEqual(action.target_data["check_in_time"], "09:30")
        self.assertEqual(action.target_data["check_out_time"], "18:00")
        self.assertFalse(Attendance.objects.filter(employee=self.employee, date=target_date).exists())

    def test_missing_employee_is_asked_then_resolved_in_followup(self):
        target_date = date.today() - timedelta(days=1)
        intent = {
            "intent": "attendance_update", "source": "attendance", "action_type": "write",
            "original_query": "Mark someone present",
            "entities": {"target_status": "PRESENT", "date_range": {"start": target_date.isoformat(), "end": target_date.isoformat()}},
        }
        session_id = views.copilot_action_session_id(self.admin.id, "test-missing-employee")
        draft = write_action_planner.plan_write_action(intent, self.admin, session_id)
        self.assertEqual(draft['status'], 'AWAITING_INFORMATION')
        self.assertIn('employee_name', draft['validation_errors'])
        conversation_id = 'test-missing-employee'
        draft['conversation_id'] = conversation_id
        action_id = pending_action_manager.store_pending_action(session_id, draft)
        request = self.factory.post('/api/hr-copilot/query/', {
            'message': 'Asha Rao, 9 AM to 6 PM', 'conversation_id': conversation_id,
        }, format='json')
        force_authenticate(request, user=self.admin)
        from unittest.mock import patch
        with patch.object(views, 'extract_pending_action_fields', return_value={
            'employee_name': 'Asha Rao', 'check_in_time': '09:00', 'check_out_time': '18:00',
        }):
            response = views.HRCopilotQueryView.as_view()(request)
        self.assertEqual(response.data['query_status'], 'pending_approval')
        action = CopilotPendingAction.objects.get(action_id=action_id)
        self.assertEqual(action.target_data['employee_id'], self.employee.id)
        self.assertTrue(action.validated)
        self.assertFalse(Attendance.objects.filter(employee=self.employee, date=target_date).exists())

    def test_exact_ashish_present_conversation_preserves_slots_until_confirmation(self):
        from unittest.mock import patch

        ashish_user = get_user_model().objects.create_user(
            email='ashish.rai@example.test', first_name='Ashish', last_name='Rai',
        )
        ashish = Employee.objects.create(
            user=ashish_user, department='Engineering', employment_type='PERMANENT',
            date_joined=date(2020, 1, 2), section='C', subsection='C1',
        )
        first_question = 'Mark Ashish Rai as present for 29th September'

        def semantic_intent(question, context=None, session_id=None):
            parsed = IntentNormalizer().normalize_intent(
                {'intent': 'attendance_update', 'entities': {}}, original_query=question,
            )
            semantic_interpreter._detect_ambiguities(parsed)
            return parsed

        conversation_id = 'ashish-attendance-slot-test'
        first_request = self.factory.post('/api/hr-copilot/query/', {
            'message': first_question, 'conversation_id': conversation_id,
        }, format='json')
        force_authenticate(first_request, user=self.admin)
        with patch.object(views, 'analyze_question', side_effect=semantic_intent):
            first_response = views.HRCopilotQueryView.as_view()(first_request)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(first_response.data['query_status'], 'awaiting_information')
        self.assertIn('Ashish Rai', first_response.data['answer'])
        self.assertIn('29 September', first_response.data['answer'])
        self.assertIn('check-in and check-out times', first_response.data['answer'])
        self.assertNotIn('couldn\'t safely prepare', first_response.data['answer'])
        pending_id = first_response.data['action_id']
        draft = CopilotPendingAction.objects.get(action_id=pending_id)
        self.assertEqual(draft.target_data['employee_id'], ashish.id)
        self.assertEqual(draft.target_data['date'], '2026-09-29')
        self.assertEqual(draft.validation_errors, ['check_in_time', 'check_out_time'])
        self.assertIsNone(draft.target_data['check_in_time'])
        self.assertIsNone(draft.target_data['check_out_time'])

        second_request = self.factory.post('/api/hr-copilot/query/', {
            'message': '9:30 AM to 6:00 PM', 'conversation_id': conversation_id,
        }, format='json')
        force_authenticate(second_request, user=self.admin)
        with patch.object(views, 'extract_pending_action_fields', return_value={
            'check_in_time': '09:30', 'check_out_time': '18:00',
        }):
            second_response = views.HRCopilotQueryView.as_view()(second_request)
        self.assertEqual(second_response.data['query_status'], 'pending_approval')
        draft.refresh_from_db()
        self.assertTrue(draft.validated)
        self.assertEqual(draft.target_data['employee_id'], ashish.id)
        self.assertEqual(draft.target_data['date'], '2026-09-29')
        self.assertEqual(draft.target_data['check_in_time'], '09:30')
        self.assertEqual(draft.target_data['check_out_time'], '18:00')
        self.assertFalse(Attendance.objects.filter(employee=ashish, date=date(2026, 9, 29)).exists())

        approve_request = self.factory.post('/api/hr-copilot/actions/approve/', {
            'action_id': str(pending_id), 'action': 'approve',
            'conversation_id': conversation_id,
        }, format='json')
        force_authenticate(approve_request, user=self.admin)
        approval_response = views.HRCopilotActionApprovalView.as_view()(approve_request)
        self.assertEqual(approval_response.status_code, 200)
        attendance = Attendance.objects.get(employee=ashish, date=date(2026, 9, 29))
        self.assertEqual(attendance.status, 'PRESENT')
        self.assertEqual(timezone.localtime(attendance.check_in).strftime('%H:%M'), '09:30')
        self.assertEqual(timezone.localtime(attendance.check_out).strftime('%H:%M'), '18:00')
        audit = CopilotActionAudit.objects.get(pending_action=draft)
        self.assertTrue(audit.success)
        self.assertTrue(audit.explicit_confirmation)

    def test_copilot_attendance_correction_preserves_historical_events(self):
        target_date = date.today() - timedelta(days=1)
        old_in = timezone.make_aware(datetime.combine(target_date, datetime.min.time()).replace(hour=9))
        old_out = timezone.make_aware(datetime.combine(target_date, datetime.min.time()).replace(hour=17))
        AttendanceEvent.objects.create(employee=self.employee, timestamp=old_in, event_type='CHECK_IN', source='MOBILE')
        AttendanceEvent.objects.create(employee=self.employee, timestamp=old_out, event_type='CHECK_OUT', source='MOBILE')
        attendance = Attendance.objects.create(employee=self.employee, date=target_date, status='PRESENT')
        attendance.recompute_from_events()

        intent = {
            'intent': 'attendance_update', 'source': 'attendance', 'action_type': 'write',
            'requires_approval': True,
            'entities': {
                'employee_email': self.employee_user.email,
                'date_range': {'start': target_date.isoformat(), 'end': target_date.isoformat()},
                'target_status': 'PRESENT', 'check_in_time': '10:00', 'check_out_time': '18:00',
            },
        }
        action_id, _ = self._plan_and_approve(intent)

        self.assertEqual(
            AttendanceEvent.objects.filter(employee=self.employee, timestamp__date=target_date).count(),
            4,
        )
        correction = AttendanceCorrection.objects.get(
            attendance__employee=self.employee, attendance__date=target_date,
            correction_type='HR_COPILOT',
        )
        self.assertEqual(correction.previous_data['copilot_action_id'], action_id)
        self.assertEqual(correction.attendance_events.count(), 2)
        attendance.refresh_from_db()
        self.assertEqual(attendance.working_duration, timedelta(hours=8))

    def test_absent_approval_clears_times_and_writes_before_after_audits(self):
        target_date = date.today() - timedelta(days=2)
        existing = Attendance.objects.create(
            employee=self.employee, date=target_date, status="PRESENT",
            check_in=timezone.make_aware(datetime.combine(target_date, datetime.min.time()).replace(hour=9)),
            check_out=timezone.make_aware(datetime.combine(target_date, datetime.min.time()).replace(hour=18)),
            working_duration=timedelta(hours=9), check_in_latitude=12.5,
        )
        AttendanceEvent.objects.create(
            employee=self.employee, timestamp=existing.check_in,
            event_type="CHECK_IN", source="MOBILE",
        )
        intent = {
            "intent": "attendance_update", "source": "attendance", "action_type": "write",
            "requires_approval": True, "original_query": "Mark Asha absent today",
            "entities": {"employee_email": self.employee_user.email,
                         "date_range": {"start": target_date.isoformat(), "end": target_date.isoformat()},
                         "target_status": "ABSENT"},
        }
        action_id, _ = self._plan_and_approve(intent)
        existing.refresh_from_db()
        self.assertEqual(existing.status, "ABSENT")
        self.assertIsNone(existing.check_in)
        self.assertIsNone(existing.check_out)
        self.assertIsNone(existing.working_duration)
        self.assertIsNone(existing.check_in_latitude)
        self.assertEqual(
            AttendanceEvent.objects.filter(employee=self.employee, timestamp__date=target_date).count(),
            1,
        )
        self.assertEqual(list(get_effective_attendance_events(self.employee, target_date)), [])
        correction = AttendanceCorrection.objects.get(attendance=existing)
        self.assertEqual(correction.previous_data["status"], "PRESENT")
        audit = CopilotActionAudit.objects.get(pending_action__action_id=action_id)
        self.assertTrue(audit.success)
        self.assertTrue(audit.explicit_confirmation)
        self.assertEqual(audit.previous_state["current_status"], "PRESENT")
        self.assertEqual(audit.new_state["status"], "ABSENT")

    def test_leave_attendance_update_requires_reason_and_keeps_leave_status(self):
        target_date = date.today() - timedelta(days=4)
        intent = {
            "intent": "attendance_update", "source": "attendance", "action_type": "write",
            "requires_approval": True,
            "original_query": "Mark Asha on leave today because of illness",
            "entities": {"employee_email": self.employee_user.email,
                         "date_range": {"start": target_date.isoformat(), "end": target_date.isoformat()},
                         "target_status": "LEAVE"},
        }
        draft = write_action_planner.plan_write_action(intent, self.admin, f"hr-copilot-user-{self.admin.id}")
        self.assertEqual(draft["status"], "AWAITING_INFORMATION")
        self.assertIn("reason", draft["validation_errors"])

        intent["entities"]["reason"] = "Medical leave"
        action_id, result = self._plan_and_approve(intent)
        attendance = Attendance.objects.get(employee=self.employee, date=target_date)
        self.assertEqual(attendance.status, "LEAVE")
        self.assertEqual(result["status"], "LEAVE")
        audit = CopilotActionAudit.objects.get(pending_action__action_id=action_id)
        self.assertEqual(audit.new_state["status"], "LEAVE")
        self.assertEqual(audit.new_state["reason"], "Medical leave")

    def test_leave_without_reason_waits_for_information(self):
        leave_type = LeaveType.objects.create(name="Annual Leave", code="TEST-REASON")
        intent = {
            "intent": "leave_create", "source": "leave", "action_type": "write",
            "entities": {"employee_email": self.employee_user.email, "target_status": "LEAVE"},
        }
        draft = write_action_planner.plan_write_action(intent, self.admin, f"hr-copilot-user-{self.admin.id}")
        self.assertEqual(draft["status"], "AWAITING_INFORMATION")
        self.assertEqual(draft["validation_errors"], ["reason"])
        self.assertFalse(LeaveRequest.objects.exists())

    def test_cancelled_action_does_not_write_and_history_is_restorable(self):
        target_date = date.today() - timedelta(days=1)
        attendance = Attendance.objects.create(employee=self.employee, date=target_date, status="INCOMPLETE")
        intent = {
            "intent": "attendance_update", "source": "attendance", "action_type": "write",
            "entities": {"employee_email": self.employee_user.email,
                         "date_range": {"start": target_date.isoformat(), "end": target_date.isoformat()},
                         "target_status": "PRESENT", "check_in_time": "09:00", "check_out_time": "18:00"},
        }
        draft = write_action_planner.plan_write_action(intent, self.admin, f"hr-copilot-user-{self.admin.id}")
        draft["conversation_id"] = "test-saved-history"
        action_id = pending_action_manager.store_pending_action(draft["session_id"], draft)
        pending_action_manager.cancel_action(draft["session_id"], action_id, self.admin.id)
        attendance.refresh_from_db()
        self.assertEqual(attendance.status, "INCOMPLETE")

        from .services.conversation import append_message
        append_message(self.admin, "test-saved-history", "user", "Show attendance")
        request = self.factory.get("/api/hr-copilot/conversations/test-saved-history/")
        force_authenticate(request, user=self.admin)
        response = views.HRCopilotConversationView.as_view()(request, conversation_id="test-saved-history")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["messages"][0]["content"], "Show attendance")

    def test_pending_action_expires_using_conversation_session(self):
        target_date = date.today() - timedelta(days=1)
        intent = {
            "intent": "attendance_update", "source": "attendance", "action_type": "write",
            "entities": {"employee_email": self.employee_user.email,
                         "date_range": {"start": target_date.isoformat(), "end": target_date.isoformat()},
                         "target_status": "PRESENT", "check_in_time": "09:00", "check_out_time": "18:00"},
        }
        conversation_id = "expiry-conversation"
        session_id = views.copilot_action_session_id(self.admin.id, conversation_id)
        draft = write_action_planner.plan_write_action(intent, self.admin, session_id)
        draft["conversation_id"] = conversation_id
        action_id = pending_action_manager.store_pending_action(session_id, draft)
        action = CopilotPendingAction.objects.get(action_id=action_id)
        action.expires_at = timezone.now() - timedelta(seconds=1)
        action.save(update_fields=["expires_at"])

        with self.assertRaises(CopilotError) as raised:
            pending_action_manager.approve_action(session_id, action_id, self.admin.id)
        self.assertEqual(raised.exception.code, "action_expired")
        action.refresh_from_db()
        self.assertEqual(action.status, "EXPIRED")

    def test_unsupported_write_intent_is_rejected_before_execution(self):
        intent = {
            "intent": "employee_update",
            "source": "employee",
            "action_type": "write",
            "entities": {},
        }
        with self.assertRaises(CopilotError) as raised:
            IntentNormalizer().normalize_intent(intent)
        self.assertEqual(raised.exception.code, "unsupported_write")

    def test_non_admin_cannot_use_copilot_write_api(self):
        request = self.factory.post("/api/hr-copilot/query/", {"message": "Mark Asha present"}, format="json")
        force_authenticate(request, user=self.employee_user)
        response = views.HRCopilotQueryView.as_view()(request)
        self.assertEqual(response.status_code, 403)

    def test_failed_attendance_transaction_rolls_back_without_success_audit(self):
        from unittest.mock import patch

        target_date = date.today() - timedelta(days=1)
        attendance = Attendance.objects.create(employee=self.employee, date=target_date, status="INCOMPLETE")
        intent = {
            "intent": "attendance_update", "source": "attendance", "action_type": "write",
            "entities": {"employee_email": self.employee_user.email,
                         "date_range": {"start": target_date.isoformat(), "end": target_date.isoformat()},
                         "target_status": "PRESENT", "check_in_time": "09:00", "check_out_time": "18:00"},
        }
        session_id = f"hr-copilot-user-{self.admin.id}"
        draft = write_action_planner.plan_write_action(intent, self.admin, session_id)
        action_id = pending_action_manager.store_pending_action(session_id, draft)
        approved = pending_action_manager.approve_action(session_id, action_id, self.admin.id)
        with patch("attendance.models.AttendanceCorrection.objects.create", side_effect=RuntimeError("audit storage unavailable")):
            with self.assertRaises(CopilotError):
                write_action_executor.execute_approved_action(approved, self.admin)
        attendance.refresh_from_db()
        self.assertEqual(attendance.status, "INCOMPLETE")
        self.assertFalse(CopilotActionAudit.objects.filter(pending_action__action_id=action_id, success=True).exists())
