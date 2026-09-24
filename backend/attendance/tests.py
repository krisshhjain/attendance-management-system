from django.test import TestCase
from rest_framework.test import APITestCase
from django.urls import reverse
from unittest.mock import patch, Mock
import requests
from django.contrib.auth import get_user_model
from employees.models import Employee, FaceProfile
from attendance.face_service import process_enrollment, find_closest_match, FaceExtractionError

User = get_user_model()

class FaceServiceIntegrationTests(TestCase):
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
        self.profile = FaceProfile.objects.create(
            employee=self.employee,
            face_template=[0.5] * 512,
            status="ACTIVE"
        )
        self.dummy_image = "dummy_base64_string"

    @patch('attendance.face_service.requests.post')
    def test_process_enrollment_success(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"template": [0.1] * 512}
        mock_post.return_value = mock_response

        template = process_enrollment(["img1", "img2", "img3"])
        self.assertEqual(template, [0.1] * 512)
        mock_post.assert_called_once()

    @patch('attendance.face_service.requests.post')
    def test_process_enrollment_multiple_faces(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "Ambiguous multi-face image"}
        mock_post.return_value = mock_response

        with self.assertRaises(FaceExtractionError) as context:
            process_enrollment(["img1", "img2", "img3"])
        self.assertIn("Ambiguous multi-face image", str(context.exception))

    @patch('attendance.face_service.requests.post')
    def test_process_enrollment_no_face(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "No faces detected"}
        mock_post.return_value = mock_response

        with self.assertRaises(FaceExtractionError) as context:
            process_enrollment(["img1", "img2", "img3"])
        self.assertIn("No faces detected", str(context.exception))

    @patch('attendance.face_service.requests.post')
    def test_find_closest_match_success(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "match",
            "employee_id": self.employee.id,
            "distance": 0.3
        }
        mock_post.return_value = mock_response

        matched_emp, distance = find_closest_match(self.dummy_image)
        self.assertEqual(matched_emp, self.employee)
        self.assertEqual(distance, 0.3)

    @patch('attendance.face_service.requests.post')
    def test_find_closest_match_unknown(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "unknown",
            "distance": 0.8
        }
        mock_post.return_value = mock_response

        matched_emp, distance = find_closest_match(self.dummy_image)
        self.assertIsNone(matched_emp)
        self.assertEqual(distance, 0.8)

    @patch('attendance.face_service.requests.post')
    def test_find_closest_match_invalid_employee(self, mock_post):
        # Service returns an ID that does not exist or isn't in candidate list
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "match",
            "employee_id": 9999,
            "distance": 0.2
        }
        mock_post.return_value = mock_response

        matched_emp, distance = find_closest_match(self.dummy_image)
        self.assertIsNone(matched_emp)

    @patch('attendance.face_service.requests.post')
    def test_service_unavailable(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        with self.assertRaises(FaceExtractionError) as context:
            find_closest_match(self.dummy_image)
        self.assertIn("service is currently unavailable", str(context.exception))

    @patch('attendance.face_service.requests.post')
    def test_service_timeout(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("Timeout")

        with self.assertRaises(FaceExtractionError) as context:
            find_closest_match(self.dummy_image)
        self.assertIn("service is currently unavailable", str(context.exception))

    @patch('attendance.face_service.requests.post')
    def test_malformed_response(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 500
        # Simulating a response where json() fails or returns missing keys handled by .get()
        mock_response.json.return_value = {"error": "Internal server error"}
        mock_post.return_value = mock_response

        with self.assertRaises(FaceExtractionError) as context:
            find_closest_match(self.dummy_image)
        self.assertIn("Internal server error", str(context.exception))

    def test_failed_enrollment_preserves_profile(self):
        # Simulate enrollment failure at view level
        original_template = self.profile.face_template
        
        with patch('attendance.face_service.requests.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.json.return_value = {"error": "No faces detected"}
            mock_post.return_value = mock_response
            
            with self.assertRaises(FaceExtractionError):
                process_enrollment(["img1", "img2", "img3"])
                
        # Check DB to ensure profile hasn't been changed or deleted
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.face_template, original_template)
        self.assertEqual(self.profile.status, "ACTIVE")

class FaceVerifyViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test2@example.com",
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
        self.profile = FaceProfile.objects.create(
            employee=self.employee,
            face_template=[0.5] * 512,
            status="ACTIVE"
        )
        self.url = reverse('verify-face')

    @patch('attendance.face_service.requests.post')
    def test_verify_known_employee(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "match", "employee_id": self.employee.id, "distance": 0.3}
        mock_post.return_value = mock_response

        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["employee_id"], self.employee.id)
        self.assertEqual(response.data["first_name"], "Test")

    @patch('attendance.face_service.requests.post')
    def test_verify_unknown_identity(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "unknown", "distance": 0.8}
        mock_post.return_value = mock_response

        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["status"], "unknown")

    @patch('attendance.face_service.requests.post')
    def test_verify_no_face(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "No faces detected"}
        mock_post.return_value = mock_response

        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("No faces detected", response.data["error"])

    @patch('attendance.face_service.requests.post')
    def test_verify_multiple_faces(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "Ambiguous multi-face image"}
        mock_post.return_value = mock_response

        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("multi-face", response.data["error"])

    @patch('attendance.face_service.requests.post')
    def test_verify_invalid_employee_id(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "match", "employee_id": 9999, "distance": 0.2}
        mock_post.return_value = mock_response

        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        self.assertEqual(response.status_code, 404)

    @patch('attendance.face_service.requests.post')
    def test_verify_inactive_employee(self, mock_post):
        self.employee.is_active = False
        self.employee.save()
        
        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        self.assertEqual(response.status_code, 404)
        mock_post.assert_not_called()
        
    @patch('attendance.face_service.requests.post')
    def test_verify_no_active_face_profile(self, mock_post):
        self.profile.status = "INACTIVE"
        self.profile.save()
        
        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        self.assertEqual(response.status_code, 404)
        mock_post.assert_not_called()

    @patch('attendance.face_service.requests.post')
    def test_verify_service_unavailable(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")
        
        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("unavailable", response.data["error"])
        
    @patch('attendance.face_service.requests.post')
    def test_verify_service_timeout(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("Timeout")
        
        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("unavailable", response.data["error"])
        
    @patch('attendance.face_service.requests.post')
    def test_verify_malformed_response(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"error": "Internal server error"}
        mock_post.return_value = mock_response

        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Internal server error", response.data["error"])
        
    def test_verify_no_image(self):
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "No image provided")

class WebsiteFacialCheckInViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test3@example.com",
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
        self.profile = FaceProfile.objects.create(
            employee=self.employee,
            face_template=[0.5] * 512,
            status="ACTIVE"
        )
        self.url = reverse('website-facial-check-in')
        
        # Second user to test spoofing
        self.user2 = User.objects.create_user(email="other@example.com", password="password123")
        self.employee2 = Employee.objects.create(user=self.user2, department="Sales", employment_type="PERMANENT", date_joined="2023-01-01")

    @patch('attendance.face_service.requests.post')
    def test_facial_check_in_success(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "match", "employee_id": self.employee.id, "distance": 0.3}
        mock_post.return_value = mock_response

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["message"], "Check-in successful")

    @patch('attendance.face_service.requests.post')
    def test_facial_check_in_mismatch(self, mock_post):
        # The FR service says it's employee1
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "match", "employee_id": self.employee.id, "distance": 0.3}
        mock_post.return_value = mock_response

        # But we are authenticated as employee2 (spoof attempt)
        self.client.force_authenticate(user=self.user2)
        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        
        self.assertEqual(response.status_code, 403)
        self.assertIn("does not match your authenticated account", response.data["error"])

    @patch('attendance.face_service.requests.post')
    def test_facial_check_in_unknown(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "unknown", "distance": 0.8}
        mock_post.return_value = mock_response

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        
        self.assertEqual(response.status_code, 403)
        self.assertIn("couldn't verify your identity", response.data["error"])

    @patch('attendance.face_service.requests.post')
    def test_facial_check_in_duplicate(self, mock_post):
        # Create a check-in for today
        from attendance.models import Attendance
        from django.utils import timezone
        Attendance.objects.create(employee=self.employee, date=timezone.localdate(), check_in=timezone.now(), status="INCOMPLETE")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "match", "employee_id": self.employee.id, "distance": 0.3}
        mock_post.return_value = mock_response

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "Already checked in today")
        
    @patch('attendance.face_service.requests.post')
    def test_facial_check_in_on_leave(self, mock_post):
        from leave_management.models import LeaveRequest, LeaveType
        from django.utils import timezone
        today = timezone.localdate()
        leave_type = LeaveType.objects.create(name="Sick Leave", description="Sick")
        LeaveRequest.objects.create(employee=self.employee, start_date=today, end_date=today, duration_days=1, status="APPROVED", leave_type=leave_type)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "match", "employee_id": self.employee.id, "distance": 0.3}
        mock_post.return_value = mock_response

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        
        self.assertEqual(response.status_code, 400)
        self.assertIn("on approved leave", response.data["error"])

    @patch('attendance.face_service.requests.post')
    def test_facial_check_in_service_unavailable(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError("Refused")
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {"image": "dummy_base64_string"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("unavailable", response.data["error"])

class WebsiteFacialCheckOutViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="out@example.com", password="password123", first_name="Test", last_name="User")
        self.employee = Employee.objects.create(user=self.user, department="Engineering", employment_type="PERMANENT", date_joined="2023-01-01")
        self.profile = FaceProfile.objects.create(employee=self.employee, face_template=[0.5] * 512, status="ACTIVE")
        self.url = reverse('website-facial-check-out')

    @patch('attendance.face_service.requests.post')
    def test_facial_check_out_success(self, mock_post):
        from attendance.models import Attendance
        from django.utils import timezone
        import datetime
        
        # Check in 6 minutes ago
        check_in_time = timezone.now() - datetime.timedelta(minutes=6)
        Attendance.objects.create(employee=self.employee, date=timezone.localdate(), check_in=check_in_time, status="INCOMPLETE")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "match", "employee_id": self.employee.id, "distance": 0.3}
        mock_post.return_value = mock_response

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {"image": "dummy"})
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["message"], "Check-out successful")

    @patch('attendance.face_service.requests.post')
    def test_facial_check_out_no_check_in(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "match", "employee_id": self.employee.id, "distance": 0.3}
        mock_post.return_value = mock_response

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {"image": "dummy"})
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "You have not checked in today")

    @patch('attendance.face_service.requests.post')
    def test_facial_check_out_cooldown(self, mock_post):
        from attendance.models import Attendance
        from django.utils import timezone
        import datetime
        
        # Checked in 2 minutes ago
        check_in_time = timezone.now() - datetime.timedelta(minutes=2)
        Attendance.objects.create(employee=self.employee, date=timezone.localdate(), check_in=check_in_time, status="INCOMPLETE")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "match", "employee_id": self.employee.id, "distance": 0.3}
        mock_post.return_value = mock_response

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {"image": "dummy"})
        
        self.assertEqual(response.status_code, 400)
        self.assertIn("Safety Cooldown", response.data["error"])

    @patch('attendance.face_service.requests.post')
    def test_facial_check_out_duplicate(self, mock_post):
        from attendance.models import Attendance
        from django.utils import timezone
        import datetime
        
        check_in_time = timezone.now() - datetime.timedelta(minutes=10)
        check_out_time = timezone.now() - datetime.timedelta(minutes=2)
        Attendance.objects.create(employee=self.employee, date=timezone.localdate(), check_in=check_in_time, check_out=check_out_time, status="PRESENT")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "match", "employee_id": self.employee.id, "distance": 0.3}
        mock_post.return_value = mock_response

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {"image": "dummy"})
        
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], "Already checked out today")

    @patch('attendance.face_service.requests.post')
    def test_facial_check_out_mismatch(self, mock_post):
        from attendance.models import Attendance
        from django.utils import timezone
        import datetime
        
        user2 = User.objects.create_user(email="other2@example.com", password="password123")
        employee2 = Employee.objects.create(user=user2, department="Sales", employment_type="PERMANENT", date_joined="2023-01-01")
        check_in_time = timezone.now() - datetime.timedelta(minutes=6)
        Attendance.objects.create(employee=employee2, date=timezone.localdate(), check_in=check_in_time, status="INCOMPLETE")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "match", "employee_id": self.employee.id, "distance": 0.3}
        mock_post.return_value = mock_response

        self.client.force_authenticate(user=user2)
        response = self.client.post(self.url, {"image": "dummy"})
        
        self.assertEqual(response.status_code, 403)
        self.assertIn("does not match your authenticated account", response.data["error"])


