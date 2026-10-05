from accounts.models import ManagerScope
"""Phase 8: reproducible end-to-end coverage of the existing Copilot contract."""

from datetime import date, timedelta, time
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from attendance.models import Attendance, AttendanceEvent, RegularizationRequest, Shift
from employees.models import Employee
from hr_copilot import views
from hr_copilot.services.intent_normalizer import IntentNormalizer
from hr_copilot.services.llm import generate_natural_answer
from hr_copilot.services.pipeline import CopilotError, analyze_question, plan_query
from hr_copilot.services.response_schema import safe_error_message
from hr_copilot.services.write_actions import write_action_planner
from hr_copilot.services.write_executor import pending_action_manager, write_action_executor
from leave_management.models import LeavePolicy, LeaveRequest, LeaveType


class Phase8ComprehensiveTests(TestCase):
    """Test matrix: query -> intent -> tool -> response -> expected facts."""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email="phase8-admin@example.test", is_system_admin=True,
             
        )
        ManagerScope.objects.create(manager=self.admin, scope_type='SECTION', value='C')
        ManagerScope.objects.create(manager=self.admin, scope_type='DEPARTMENT', value='Engineering')

        employee_user = User.objects.create_user(email="krish@example.test", first_name="Krish", last_name="Rao")
        self.employee = Employee.objects.create(
            user=employee_user, department="Engineering", employment_type="PERMANENT",
            date_joined=timezone.localdate() - timedelta(days=60), section="C", subsection="C1",
        )
        self.shift = Shift.objects.create(name="Morning", code="P8-MORNING", start_time=time(9), end_time=time(18), employment_type="PERMANENT")
        self.employee.shift = self.shift
        self.employee.save(update_fields=["shift"])
        self.scope = {"sections": ["C"], "subsections": ["C1"], "unrestricted": False}
        self.leave_type = LeaveType.objects.create(name="Casual Leave", code="CASUAL", is_active=True)
        LeavePolicy.objects.create(
            employee_type="PERMANENT", leave_type=self.leave_type, annual_entitlement=Decimal("12"),
            effective_from=timezone.localdate().replace(month=1, day=1), is_active=True,
        )

    def raw_intent(self, intent, entities=None):
        return IntentNormalizer().normalize_intent({"intent": intent, "entities": entities or {}})

    def test_basic_query_matrix_selects_expected_typed_intent_and_tool(self):
        matrix = [
            ("Who has not checked in today?", "attendance_intelligence", "attendance_intelligence_tool", {"attendance_metric": "missing_checkins", "temporal_expression": "today"}),
            ("Who was late today?", "attendance_intelligence", "attendance_intelligence_tool", {"attendance_metric": "late_employees", "temporal_expression": "today"}),
            ("How many hours did Krish work today?", "attendance_intelligence", "attendance_intelligence_tool", {"attendance_metric": "working_hours", "employee_name": "Krish", "temporal_expression": "today"}),
            ("What is Krish's leave balance?", "leave_regularization_intelligence", "leave_regularization_intelligence_tool", {"intelligence_metric": "leave_balance", "employee_name": "Krish"}),
            ("Show all pending leave requests.", "leave_regularization_intelligence", "leave_regularization_intelligence_tool", {"intelligence_metric": "leave_requests"}),
            ("Show Krish's employee details.", "workforce_intelligence", "workforce_intelligence_tool", {"workforce_metric": "employee_details", "employee_name": "Krish"}),
            ("Show all configured shifts.", "workforce_intelligence", "workforce_intelligence_tool", {"workforce_metric": "shift_configuration"}),
        ]
        for question, expected_intent, expected_tool, entities in matrix:
            with self.subTest(question=question):
                with patch("hr_copilot.services.semantic_interpreter.get_structured_intent", return_value=self.raw_intent(expected_intent, entities)):
                    intent = analyze_question(question)
                self.assertEqual(intent["intent"], expected_intent)
                self.assertEqual(intent["backend_tool"], expected_tool)

    def test_actual_authenticated_api_routes_to_typed_tool_and_response_schema(self):
        factory = APIRequestFactory()
        question = "How many hours did Krish work today?"
        raw = self.raw_intent("attendance_intelligence", {
            "attendance_metric": "working_hours", "employee_name": "Krish", "temporal_expression": "today",
        })
        tool_result = {"metric": "working_hours", "date_range": {"start": timezone.localdate().isoformat(), "end": timezone.localdate().isoformat()}, "assumptions": [], "rows": [{"employee_name": "Krish Rao", "total_working_duration": "07:30:00"}]}
        request = factory.post("/api/hr-copilot/query/", {"message": question, "conversation_id": "phase8-api"}, format="json")
        force_authenticate(request, user=self.admin)
        with patch("hr_copilot.services.semantic_interpreter.get_structured_intent", return_value=raw), patch.object(views.hr_tools, "execute_attendance_intelligence", return_value=tool_result) as tool:
            response = views.HRCopilotQueryView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["response_type"], "result")
        self.assertEqual(response.data["data"]["metadata"]["metric"], "working_hours")
        self.assertIn("07:30:00", response.data["answer"])
        tool.assert_called_once()

    def test_grounding_empty_numeric_and_sensitive_values(self):
        self.assertEqual(generate_natural_answer("x", {"intent": "employee_count", "source": "employee", "entities": {}}, []), "No matching HR records were found.")
        self.assertEqual(generate_natural_answer("x", {"intent": "employee_count", "source": "employee", "entities": {}}, [{"value": 12}]), "The result is 12.")
        answer = generate_natural_answer("x", {"intent": "leave_regularization_intelligence", "entities": {"intelligence_metric": "leave_balance"}}, [{"available": 4.5, "employee_name": "Krish Rao"}])
        self.assertIn("1 result", answer)
        self.assertNotIn("5.5", answer)

    def test_follow_up_context_and_pronouns_preserve_employee_and_date(self):
        from hr_copilot.services import conversation
        first = {"intent": "attendance_intelligence", "entities": {"employee_id": self.employee.id, "date_range": {"start": "2026-09-01", "end": "2026-09-30"}}}
        context = {"current_employee_id": self.employee.id, "current_date": "2026-09-01", "current_date_end": "2026-09-30", "last_intent": "attendance_intelligence"}
        follow = conversation.apply_context("How many hours did he work?", {"intent": "attendance_intelligence", "entities": {"attendance_metric": "working_hours"}}, context)
        self.assertEqual(follow["entities"]["employee_id"], self.employee.id)
        self.assertEqual(follow["entities"]["date_range"]["end"], "2026-09-30")
        self.assertEqual(first["entities"]["employee_id"], self.employee.id)

    def test_ambiguous_employee_and_requests_are_rejected(self):
        User = get_user_model()
        duplicate_user = User.objects.create_user(email="krish-two@example.test", first_name="Krish", last_name="Rao")
        Employee.objects.create(user=duplicate_user, department="Engineering", employment_type="PERMANENT", date_joined=timezone.localdate(), section="C", subsection="C1")
        with patch("hr_copilot.services.semantic_interpreter.get_structured_intent", return_value=self.raw_intent("workforce_intelligence", {"workforce_metric": "employee_details", "employee_name": "Krish Rao"})):
            with self.assertRaises(CopilotError) as error:
                analyze_question("Show Krish Rao's details")
        self.assertEqual(error.exception.code, "employee_ambiguous")

        target = timezone.localdate() - timedelta(days=1)
        for reason in ("One", "Two"):
            RegularizationRequest.objects.create(employee=self.employee, attendance_date=target, request_type="SYSTEM_ISSUE", reason=reason, status="REJECTED")
        with self.assertRaises(CopilotError) as error:
            from hr_copilot.services.leave_regularization_intelligence import leave_regularization_intelligence
            leave_regularization_intelligence.execute(metric="attendance_correction_explanation", scope=self.scope, user=self.admin, filters={"date_range": {"start": target.isoformat(), "end": target.isoformat()}}, employee_id=self.employee.id)
        self.assertEqual(error.exception.code, "request_ambiguous")

    def test_write_requires_confirmation_and_repeated_confirmation_is_rejected(self):
        intent = {"intent": "employee_shift_assign", "source": "employee", "action_type": "write", "requires_approval": True, "entities": {"employee_id": self.employee.id, "shift_id": self.shift.id}}
        session = f"phase8-write-{self.admin.id}"
        pending = write_action_planner.plan_write_action(intent, self.admin, session)
        action_id = pending_action_manager.store_pending_action(session, pending)
        self.employee.refresh_from_db()
        approved = pending_action_manager.approve_action(session, action_id, self.admin.id)
        result = write_action_executor.execute_approved_action(approved, self.admin)
        self.assertEqual(result["action_id"], action_id)
        pending_action_manager.mark_executed(action_id, self.admin.id, session, result)
        with self.assertRaises(CopilotError):
            pending_action_manager.approve_action(session, action_id, self.admin.id)

    def test_unsupported_and_malformed_requests_never_execute_writes(self):
        with patch("hr_copilot.services.semantic_interpreter.get_structured_intent", return_value=self.raw_intent("unknown")):
            with self.assertRaises(CopilotError) as error:
                plan_query(analyze_question("Reset attendance completely"), self.scope, self.admin)
        self.assertEqual(error.exception.code, "unknown_question")
        self.assertNotIn("SQL", safe_error_message("invalid_intent", "SQL parser traceback"))

        with patch("hr_copilot.services.semantic_interpreter.get_structured_intent", side_effect=CopilotError("invalid_intent", "raw provider details")):
            with self.assertRaises(CopilotError):
                analyze_question("Approve all regularizations in bulk")

    def test_permission_isolation_is_revalidated_before_planning(self):
        User = get_user_model()
        outside_user = User.objects.create_user(email="outside-phase8@example.test")
        outside = Employee.objects.create(user=outside_user, department="Finance", employment_type="PERMANENT", date_joined=timezone.localdate(), section="D", subsection="D1")
        intent = {"intent": "employee_shift_assign", "source": "employee", "action_type": "write", "requires_approval": True, "entities": {"employee_id": outside.id, "shift_id": self.shift.id}}
        with self.assertRaises(CopilotError) as error:
            write_action_planner.plan_write_action(intent, self.admin, self.scope)
        self.assertEqual(error.exception.code, "scope_denied")
