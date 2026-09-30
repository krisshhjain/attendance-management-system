from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from datetime import datetime

from attendance.models import RegularizationRequest
from employees.models import Employee
from hr_copilot.services.leave_regularization_intelligence import leave_regularization_intelligence
from hr_copilot.services.pipeline import CopilotError, analyze_question
from leave_management.models import LeavePolicy, LeaveRequest, LeaveType


class LeaveRegularizationIntelligenceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email="leave-copilot-admin@example.test", is_system_admin=True,
            hr_copilot_sections=["C"], hr_copilot_subsections=["C1"],
        )
        self.user = User.objects.create_user(email="leave-employee@example.test", first_name="Asha", last_name="Rao")
        self.employee = Employee.objects.create(
            user=self.user, department="Engineering", employment_type="PERMANENT",
            date_joined=timezone.localdate() - timedelta(days=30), section="C", subsection="C1",
        )
        other_user = User.objects.create_user(email="leave-other@example.test", first_name="Other")
        self.other = Employee.objects.create(
            user=other_user, department="Engineering", employment_type="PERMANENT",
            date_joined=timezone.localdate() - timedelta(days=30), section="D", subsection="D1",
        )
        self.scope = {"sections": ["C"], "subsections": ["C1"], "unrestricted": False}
        self.leave_type = LeaveType.objects.create(name="Annual", code="ANNUAL", is_active=True)
        LeavePolicy.objects.create(
            employee_type="PERMANENT", leave_type=self.leave_type, annual_entitlement=Decimal("20"),
            effective_from=timezone.localdate().replace(month=1, day=1), is_active=True,
        )

    def leave(self, employee, status="APPROVED", days=2):
        start = timezone.localdate() + timedelta(days=7 + LeaveRequest.objects.count())
        return LeaveRequest.objects.create(
            employee=employee, leave_type=self.leave_type, start_date=start,
            end_date=start + timedelta(days=days - 1), duration_days=Decimal(str(days)),
            reason="Personal", status=status,
        )

    def test_leave_balance_uses_application_calculator(self):
        self.leave(self.employee, "APPROVED", 2)
        self.leave(self.employee, "PENDING", 1)
        result = leave_regularization_intelligence.execute(
            metric="leave_balance", scope=self.scope, user=self.admin,
            filters={}, employee_id=self.employee.id,
        )
        row = result["rows"][0]
        self.assertEqual(row["used"], 2.0)
        self.assertEqual(row["pending"], 1.0)
        self.assertEqual(row["available"], 18.0)

    def test_leave_queries_policy_and_scope(self):
        self.leave(self.employee, "PENDING", 1)
        self.leave(self.other, "PENDING", 1)
        result = leave_regularization_intelligence.execute(
            metric="leave_requests", scope=self.scope, user=self.admin, filters={},
        )
        self.assertEqual([row["employee_id"] for row in result["rows"]], [self.employee.id])
        policy = leave_regularization_intelligence.execute(
            metric="leave_policy", scope=self.scope, user=self.admin, filters={},
        )
        self.assertTrue(policy["rows"])
        with self.assertRaises(CopilotError) as error:
            leave_regularization_intelligence.execute(
                metric="leave_balance", scope=self.scope, user=self.admin, filters={}, employee_id=self.other.id,
            )
        self.assertEqual(error.exception.code, "scope_denied")

    def test_regularization_queries_and_correction_explanation(self):
        target = timezone.localdate() - timedelta(days=1)
        req = RegularizationRequest.objects.create(
            employee=self.employee, attendance_date=target, request_type="FORGOT_CHECK_OUT",
            requested_check_in=timezone.make_aware(datetime.combine(target, datetime.min.time()).replace(hour=9)), reason="Forgot checkout", status="PENDING",
        )
        pending = leave_regularization_intelligence.execute(
            metric="regularization_pending", scope=self.scope, user=self.admin,
            filters={}, employee_id=self.employee.id,
        )
        self.assertEqual(pending["rows"][0]["id"], req.id)
        history = leave_regularization_intelligence.execute(
            metric="regularization_history", scope=self.scope, user=self.admin,
            filters={"date_range": {"start": target.isoformat(), "end": target.isoformat()}}, employee_id=self.employee.id,
        )
        self.assertEqual(history["rows"][0]["status"], "PENDING")

    def test_ambiguous_regularization_requires_request_id(self):
        target = timezone.localdate() - timedelta(days=1)
        for reason in ("First", "Second"):
            RegularizationRequest.objects.create(
                employee=self.employee, attendance_date=target, request_type="SYSTEM_ISSUE",
                reason=reason, status="REJECTED",
            )
        with self.assertRaises(CopilotError) as error:
            leave_regularization_intelligence.execute(
                metric="attendance_correction_explanation", scope=self.scope, user=self.admin,
                filters={"date_range": {"start": target.isoformat(), "end": target.isoformat()}}, employee_id=self.employee.id,
            )
        self.assertEqual(error.exception.code, "request_ambiguous")

    def test_semantic_layer_uses_typed_leave_metric(self):
        with patch("hr_copilot.services.semantic_interpreter.get_structured_intent", return_value={
            "intent": "leave_regularization_intelligence",
            "entities": {"intelligence_metric": "leave_balance", "employee_id": self.employee.id},
        }):
            intent = analyze_question("What is Asha's remaining leave balance?")
        self.assertEqual(intent["intent"], "leave_regularization_intelligence")
        self.assertEqual(intent["entities"]["intelligence_metric"], "leave_balance")
