from datetime import timedelta, time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from attendance.models import OfficeLocation, Shift
from employees.models import Employee, FaceProfile
from hr_copilot.services.pipeline import CopilotError, analyze_question
from hr_copilot.services.workforce_intelligence import workforce_intelligence
from hr_copilot.services.llm import generate_natural_answer
from hr_copilot.services.intent_normalizer import IntentNormalizer
from hr_copilot.services.semantic_interpreter import semantic_interpreter
from hr_copilot.services.conversation import load_context, save_context


class WorkforceIntelligenceTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            email="workforce-admin@example.test", is_system_admin=True,
            hr_copilot_sections=["C"], hr_copilot_subsections=["C1"],
        )
        self.user = User.objects.create_user(email="workforce-employee@example.test", first_name="Asha", last_name="Rao")
        self.employee = Employee.objects.create(
            user=self.user, department="Engineering", employment_type="PERMANENT",
            date_joined=timezone.localdate() - timedelta(days=30), section="C", subsection="C1",
        )
        other_user = User.objects.create_user(email="workforce-outside@example.test", first_name="Other")
        self.other = Employee.objects.create(
            user=other_user, department="Finance", employment_type="PERMANENT",
            date_joined=timezone.localdate() - timedelta(days=30), section="D", subsection="D1",
        )
        self.scope = {"sections": ["C"], "subsections": ["C1"], "unrestricted": False}

    def test_employee_details_and_scope(self):
        result = workforce_intelligence.execute(
            metric="employee_details", scope=self.scope, user=self.admin, filters={}, employee_id=self.employee.id,
        )
        self.assertEqual(result["rows"][0]["email"], self.user.email)
        with self.assertRaises(CopilotError) as error:
            workforce_intelligence.execute(
                metric="employee_details", scope=self.scope, user=self.admin, filters={}, employee_id=self.other.id,
            )
        self.assertEqual(error.exception.code, "scope_denied")

    def test_org_counts_shift_and_face_enrollment(self):
        shift = Shift.objects.create(name="Morning", code="WF-MORNING", start_time=time(9), end_time=time(18), is_active=True)
        self.employee.shift = shift
        self.employee.save(update_fields=["shift"])
        FaceProfile.objects.create(employee=self.employee, face_template=[0.1], status="ACTIVE")
        counts = workforce_intelligence.execute(metric="org_counts", scope=self.scope, user=self.admin, filters={})
        self.assertTrue(any(row["value"] == "Engineering" for row in counts["rows"]))
        assignments = workforce_intelligence.execute(metric="shift_assignments", scope=self.scope, user=self.admin, filters={})
        self.assertEqual(assignments["rows"][0]["employee_id"], self.employee.id)
        configuration = workforce_intelligence.execute(metric="shift_configuration", scope=self.scope, user=self.admin, filters={})
        self.assertEqual(configuration["rows"][0]["assigned_employee_count"], 1)
        enrolled = workforce_intelligence.execute(metric="face_enrollment", scope=self.scope, user=self.admin, filters={"face_enrolled": True})
        self.assertEqual(enrolled["rows"][0]["employee_id"], self.employee.id)
        missing = workforce_intelligence.execute(metric="face_enrollment", scope=self.scope, user=self.admin, filters={"face_enrolled": False})
        self.assertEqual(missing["rows"], [])

    def test_employee_specific_shift_assignment_returns_one_employee(self):
        shift = Shift.objects.create(name="Morning", code="WF-MORNING", start_time=time(9), end_time=time(18), is_active=True)
        self.employee.shift = shift
        self.employee.save(update_fields=["shift"])
        result = workforce_intelligence.execute(
            metric="shift_assignments", scope=self.scope, user=self.admin, filters={}, employee_id=self.employee.id,
        )
        self.assertEqual(len(result["rows"]), 1)
        self.assertEqual(result["rows"][0]["assigned_shift_name"], "Morning")

    def test_employee_without_shift_is_explicitly_unassigned(self):
        result = workforce_intelligence.execute(
            metric="shift_assignments", scope=self.scope, user=self.admin, filters={}, employee_id=self.employee.id,
        )
        self.assertEqual(result["rows"][0]["assigned_shift_name"], None)
        answer = generate_natural_answer(
            "What shift is Asha assigned to?",
            {"entities": {"workforce_metric": "shift_assignments"}},
            result["rows"],
        )
        self.assertIn("no shift assigned", answer)

    def test_shift_query_resolves_exact_email_and_name(self):
        for question, entities in (
            ("What shift is workforce-employee@example.test assigned to?", {
                "workforce_metric": "shift_assignments", "employee_email": self.user.email,
            }),
            ("What shift is Asha assigned to?", {
                "workforce_metric": "shift_assignments", "employee_name": "Asha",
            }),
        ):
            with self.subTest(question=question), patch(
                "hr_copilot.services.semantic_interpreter.get_structured_intent",
                return_value={"intent": "workforce_intelligence", "entities": entities},
            ):
                intent = analyze_question(question)
            self.assertEqual(intent["entities"]["employee_id"], self.employee.id)
            self.assertEqual(intent["entities"]["workforce_metric"], "shift_assignments")

    def test_shift_assignment_filter_returns_employees_not_configuration(self):
        shift = Shift.objects.create(name="Morning", code="WF-MORNING", start_time=time(9), end_time=time(18), is_active=True)
        self.employee.shift = shift
        self.employee.save(update_fields=["shift"])
        result = workforce_intelligence.execute(
            metric="shift_assignments", scope=self.scope, user=self.admin,
            filters={"shift_name": "Morning"},
        )
        self.assertEqual([row["employee_id"] for row in result["rows"]], [self.employee.id])
        self.assertNotIn("assigned_employee_count", result["rows"][0])

    def test_natural_shift_filter_is_not_configuration_query(self):
        intent = IntentNormalizer().normalize_intent(
            {"intent": "employee_lookup", "entities": {}},
            "Who is assigned to Morning shift?",
        )
        self.assertEqual(intent["intent"], "workforce_intelligence")
        self.assertEqual(intent["entities"]["workforce_metric"], "shift_assignments")
        self.assertEqual(intent["entities"]["shift_name"], "morning")

    def test_superuser_can_read_employee_outside_manager_scope(self):
        superuser = get_user_model().objects.create_superuser(
            email="workforce-superuser@example.test", password="test-password",
        )
        result = workforce_intelligence.execute(
            metric="shift_assignments", scope={"sections": None, "subsections": None, "unrestricted": True},
            user=superuser, filters={}, employee_id=self.other.id,
        )
        self.assertEqual(result["rows"][0]["employee_id"], self.other.id)

    def test_follow_up_name_reuses_established_employee_without_global_lookup(self):
        with patch(
            "hr_copilot.services.semantic_interpreter.get_structured_intent",
            return_value={"intent": "workforce_intelligence", "entities": {"workforce_metric": "shift_assignments", "employee_name": "Asha"}},
        ), patch("hr_copilot.services.employee_resolver.employee_resolver.resolve_employee") as resolver:
            intent = semantic_interpreter.interpret_query(
                "What shift is Asha assigned to?",
                {"current_employee_id": self.employee.id, "current_employee_name": "Asha Rao"},
            )
        self.assertEqual(intent["entities"]["employee_id"], self.employee.id)
        resolver.assert_not_called()

    def test_email_context_is_persisted_with_safe_identity_fields(self):
        save_context(
            self.admin, "shift-context",
            {"employee": {"employee_id": self.employee.id}, "filters": {}, "intent": "workforce_intelligence", "workforce_metric": "shift_assignments"},
        )
        context = load_context(self.admin, "shift-context")
        self.assertEqual(context["current_employee_id"], self.employee.id)
        self.assertEqual(context["current_employee_name"], "Asha Rao")
        self.assertEqual(context["current_employee_email"], self.user.email)

    def test_context_switches_for_explicit_new_email(self):
        other_user = get_user_model().objects.get(email="workforce-outside@example.test")
        with patch(
            "hr_copilot.services.semantic_interpreter.get_structured_intent",
            return_value={"intent": "workforce_intelligence", "entities": {"workforce_metric": "shift_assignments", "employee_email": other_user.email}},
        ):
            intent = semantic_interpreter.interpret_query(
                f"What shift is {other_user.email} assigned to?",
                {"current_employee_id": self.employee.id, "current_employee_email": self.user.email},
            )
        self.assertEqual(intent["entities"]["employee_id"], self.other.id)

    def test_duplicate_name_without_context_requires_clarification(self):
        duplicate_user = get_user_model().objects.create_user(email="workforce-duplicate@example.test", first_name="Asha", last_name="Rao")
        Employee.objects.create(
            user=duplicate_user, department="Engineering", employment_type="PERMANENT",
            date_joined=timezone.localdate(), section="C", subsection="C1",
        )
        with patch(
            "hr_copilot.services.semantic_interpreter.get_structured_intent",
            return_value={"intent": "workforce_intelligence", "entities": {"workforce_metric": "shift_assignments", "employee_name": "Asha"}},
        ):
            intent = semantic_interpreter.interpret_query("What shift is Asha assigned to?", {})
        self.assertIn("employee_identity", intent["ambiguities"])

    def test_access_and_office_location_queries(self):
        location = OfficeLocation.objects.create(name="HQ", latitude=1.0, longitude=2.0, radius_meters=100)
        access = workforce_intelligence.execute(metric="access_status", scope=self.scope, user=self.admin, filters={"access_key": "leave"})
        self.assertTrue(access["rows"][0]["access_enabled"])
        locations = workforce_intelligence.execute(metric="office_locations", scope=self.scope, user=self.admin, filters={})
        self.assertEqual(locations["rows"][0]["id"], location.id)

    def test_ambiguous_employee_is_rejected_by_semantic_pipeline(self):
        duplicate_user = get_user_model().objects.create_user(email="duplicate@example.test", first_name="Asha", last_name="Rao")
        Employee.objects.create(
            user=duplicate_user, department="Engineering", employment_type="PERMANENT",
            date_joined=timezone.localdate(), section="C", subsection="C1",
        )
        with patch("hr_copilot.services.semantic_interpreter.get_structured_intent", return_value={
            "intent": "workforce_intelligence",
            "entities": {"workforce_metric": "employee_details", "employee_name": "Asha Rao"},
        }):
            with self.assertRaises(CopilotError) as error:
                analyze_question("Show Asha Rao's employee details")
        self.assertEqual(error.exception.code, "employee_ambiguous")

    def test_natural_variation_uses_one_typed_workforce_metric(self):
        with patch("hr_copilot.services.semantic_interpreter.get_structured_intent", return_value={
            "intent": "employee_lookup",
            "entities": {"workforce_metric": "face_enrollment"},
        }):
            intent = analyze_question("Which employees have not enrolled a face?")
        self.assertEqual(intent["intent"], "workforce_intelligence")
        self.assertEqual(intent["entities"]["workforce_metric"], "face_enrollment")
