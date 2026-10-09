from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.core.management import call_command, CommandError
from io import StringIO
from unittest.mock import patch
from employees.models import Employee, FaceProfile

User = get_user_model()

class FaceProfileModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test@example.com",
            password="password123",
            first_name="Test",
            last_name="User"
        )
        self.employee = Employee.objects.create(
            user=self.user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined="2023-01-01"
        )
        self.dummy_template = [0.1] * 512

    def test_create_face_profile(self):
        """Test creating a FaceProfile securely attaches to Employee."""
        profile = FaceProfile.objects.create(
            employee=self.employee,
            face_template=self.dummy_template,
            model_name="ArcFace",
            detector_backend="retinaface",
            version="1.0",
            status="ACTIVE"
        )
        self.assertEqual(profile.employee, self.employee)
        self.assertEqual(profile.status, "ACTIVE")
        self.assertEqual(len(profile.face_template), 512)

    def test_one_to_one_constraint(self):
        """Test that an employee cannot have multiple FaceProfile rows (integrity error)."""
        FaceProfile.objects.create(
            employee=self.employee,
            face_template=self.dummy_template
        )
        
        with self.assertRaises(IntegrityError):
            FaceProfile.objects.create(
                employee=self.employee,
                face_template=self.dummy_template
            )

    def test_update_existing_profile(self):
        """Test updating an existing profile via update_or_create."""
        profile, created = FaceProfile.objects.update_or_create(
            employee=self.employee,
            defaults={
                "face_template": self.dummy_template,
                "status": "ACTIVE"
            }
        )
        self.assertTrue(created)
        
        new_template = [0.5] * 512
        profile2, created2 = FaceProfile.objects.update_or_create(
            employee=self.employee,
            defaults={
                "face_template": new_template,
                "status": "ACTIVE",
                "version": "1.1"
            }
        )
        self.assertFalse(created2)
        self.assertEqual(profile.pk, profile2.pk)
        self.assertEqual(profile2.face_template, new_template)
        self.assertEqual(profile2.version, "1.1")


class CredentialBootstrapCommandTests(TestCase):
    """Reference-data commands must never assign predictable passwords."""

    def _assert_account_has_no_password(self, email):
        user = User.objects.get(email=email)
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.check_password("Security@123"))
        self.assertTrue(user.employee.must_change_password)

    @patch(
        "employees.management.commands.import_reference_students.STUDENTS",
        [("Security Test", "A", "A1")],
    )
    def test_import_command_creates_account_without_usable_password(self):
        call_command("import_reference_students", stdout=StringIO())
        self._assert_account_has_no_password("security.test@dailoqa.com")

    @patch(
        "employees.management.commands.restore_checkpoint_students.STUDENTS",
        [("Security Test", "A", "A1")],
    )
    def test_restore_command_creates_account_without_usable_password(self):
        call_command("restore_checkpoint_students", stdout=StringIO())
        self._assert_account_has_no_password("security.test@dailoqa.com")

    def test_bulk_reset_requires_confirmation_and_disables_passwords(self):
        user = User.objects.create_user(
            email="bulk-reset@example.com", password="ExistingPassword123!", first_name=""
        )
        Employee.objects.create(
            user=user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined="2023-01-01",
            must_change_password=False,
        )

        with self.assertRaises(CommandError):
            call_command("reset_all_passwords", stdout=StringIO())

        call_command("reset_all_passwords", confirm=True, stdout=StringIO())
        user.refresh_from_db()
        self.assertFalse(user.has_usable_password())
        self.assertTrue(user.employee.must_change_password)
