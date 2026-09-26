from datetime import date, timedelta
from unittest.mock import patch, Mock
import requests
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from employees.models import Employee, FaceProfile
from attendance.models import Attendance
from attendance.geofence import (
    WORKPLACE_LATITUDE,
    WORKPLACE_LONGITUDE,
    GEOFENCE_RADIUS_METERS,
    MAX_ACCURACY_METERS,
    calculate_haversine_distance,
)
from attendance.face_service import process_enrollment, find_closest_match, FaceExtractionError

User = get_user_model()


class AttendanceGeofenceTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="employee@example.com",
            password="password123",
        )
        self.employee = Employee.objects.create(
            user=self.user,
            department="Engineering",
            employment_type="PERMANENT",
            date_joined=date.today(),
            is_active=True,
        )
        self.client.force_authenticate(user=self.user)

        self.valid_location = {
            "latitude": WORKPLACE_LATITUDE,
            "longitude": WORKPLACE_LONGITUDE,
            "accuracy": 15.0,
        }

        # Point ~22km north of workplace — guaranteed outside any sane geofence radius
        self.outside_location = {
            "latitude": WORKPLACE_LATITUDE + 0.2,
            "longitude": WORKPLACE_LONGITUDE,
            "accuracy": 10.0,
        }

        # Poor accuracy — exceeds MAX_ACCURACY_METERS (500m in env, 200m in code default)
        self.low_accuracy_location = {
            "latitude": WORKPLACE_LATITUDE,
            "longitude": WORKPLACE_LONGITUDE,
            "accuracy": 600.0,
        }

    def test_haversine_distance_calculation(self):
        dist_same = calculate_haversine_distance(
            WORKPLACE_LATITUDE, WORKPLACE_LONGITUDE,
            WORKPLACE_LATITUDE, WORKPLACE_LONGITUDE
        )
        self.assertAlmostEqual(dist_same, 0.0, places=1)

        dist_outside = calculate_haversine_distance(
            self.outside_location["latitude"], self.outside_location["longitude"],
            WORKPLACE_LATITUDE, WORKPLACE_LONGITUDE
        )
        # The outside_location is ~22km away; assert it is genuinely far
        self.assertGreater(dist_outside, 1000.0)

    def test_check_in_successful_inside_geofence(self):
        response = self.client.post("/api/attendance/check-in/", self.valid_location, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["message"], "Attendance marked successfully.")
        
        record = Attendance.objects.get(employee=self.employee, date=timezone.localdate())
        self.assertIsNotNone(record.check_in)
        self.assertEqual(record.status, "INCOMPLETE")
        self.assertEqual(record.check_in_latitude, WORKPLACE_LATITUDE)
        self.assertEqual(record.check_in_longitude, WORKPLACE_LONGITUDE)
        self.assertIsNotNone(record.check_in_distance)
        self.assertLessEqual(record.check_in_distance, GEOFENCE_RADIUS_METERS)

    def test_check_in_rejected_outside_geofence(self):
        response = self.client.post("/api/attendance/check-in/", self.outside_location, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("outside the allowed attendance area", response.data["error"])
        self.assertFalse(Attendance.objects.filter(employee=self.employee).exists())

    def test_check_in_rejected_poor_accuracy(self):
        response = self.client.post("/api/attendance/check-in/", self.low_accuracy_location, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["error"],
            "Your location accuracy is too low. Please enable precise location and try again."
        )

    def test_check_in_rejected_missing_coordinates(self):
        response = self.client.post("/api/attendance/check-in/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Location coordinates", response.data["error"])

    def test_check_out_inside_geofence(self):
        # Create an attendance record checked in 10 minutes ago
        past_time = timezone.now() - timedelta(minutes=10)
        record = Attendance.objects.create(
            employee=self.employee,
            date=timezone.localdate(),
            check_in=past_time,
            status="INCOMPLETE",
        )

        response = self.client.post("/api/attendance/check-out/", self.valid_location, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Check-out successful")

        record.refresh_from_db()
        self.assertEqual(record.status, "PRESENT")
        self.assertIsNotNone(record.check_out)
        self.assertEqual(record.check_out_latitude, WORKPLACE_LATITUDE)
        self.assertLessEqual(record.check_out_distance, GEOFENCE_RADIUS_METERS)

    def test_check_out_rejected_outside_geofence(self):
        past_time = timezone.now() - timedelta(minutes=10)
        Attendance.objects.create(
            employee=self.employee,
            date=timezone.localdate(),
            check_in=past_time,
            status="INCOMPLETE",
        )

        response = self.client.post("/api/attendance/check-out/", self.outside_location, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("outside the allowed attendance area", response.data["error"])

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
        self.valid_location = {
            "latitude": WORKPLACE_LATITUDE,
            "longitude": WORKPLACE_LONGITUDE,
            "accuracy": 15.0,
        }
        
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
        response = self.client.post(self.url, {"image": "dummy_base64_string", **self.valid_location})
        
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
        response = self.client.post(self.url, {"image": "dummy_base64_string", **self.valid_location})
        
        self.assertEqual(response.status_code, 403)
        self.assertIn("does not match your authenticated account", response.data["error"])

    @patch('attendance.face_service.requests.post')
    def test_facial_check_in_unknown(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "unknown", "distance": 0.8}
        mock_post.return_value = mock_response

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {"image": "dummy_base64_string", **self.valid_location})
        
        self.assertEqual(response.status_code, 403)
        # verify_employee_face does 1:1 check — an unrecognised face returns the same mismatch message
        self.assertIn("does not match your authenticated account", response.data["error"])

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
        response = self.client.post(self.url, {"image": "dummy_base64_string", **self.valid_location})
        
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
        response = self.client.post(self.url, {"image": "dummy_base64_string", **self.valid_location})
        
        self.assertEqual(response.status_code, 400)
        self.assertIn("on approved leave", response.data["error"])

    @patch('attendance.face_service.requests.post')
    def test_facial_check_in_rejected_outside_geofence(self, mock_post):
        # Use a point ~22km away — guaranteed to exceed any reasonable geofence radius
        outside_location = {
            "latitude": WORKPLACE_LATITUDE + 0.2,
            "longitude": WORKPLACE_LONGITUDE,
            "accuracy": 10.0,
        }
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {"image": "dummy_base64_string", **outside_location})
        self.assertEqual(response.status_code, 400)
        self.assertIn("outside the allowed attendance area", response.data["error"])
        mock_post.assert_not_called()

    @patch('attendance.face_service.requests.post')
    def test_facial_check_in_service_unavailable(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError("Refused")
        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {"image": "dummy_base64_string", **self.valid_location})
        self.assertEqual(response.status_code, 400)
        self.assertIn("unavailable", response.data["error"])

class WebsiteFacialCheckOutViewTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="out@example.com", password="password123", first_name="Test", last_name="User")
        self.employee = Employee.objects.create(user=self.user, department="Engineering", employment_type="PERMANENT", date_joined="2023-01-01")
        self.profile = FaceProfile.objects.create(employee=self.employee, face_template=[0.5] * 512, status="ACTIVE")
        self.url = reverse('website-facial-check-out')
        self.valid_location = {
            "latitude": WORKPLACE_LATITUDE,
            "longitude": WORKPLACE_LONGITUDE,
            "accuracy": 15.0,
        }

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
        response = self.client.post(self.url, {"image": "dummy", **self.valid_location})
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["message"], "Check-out successful")

    @patch('attendance.face_service.requests.post')
    def test_facial_check_out_no_check_in(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "match", "employee_id": self.employee.id, "distance": 0.3}
        mock_post.return_value = mock_response

        self.client.force_authenticate(user=self.user)
        response = self.client.post(self.url, {"image": "dummy", **self.valid_location})
        
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
        response = self.client.post(self.url, {"image": "dummy", **self.valid_location})
        
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
        response = self.client.post(self.url, {"image": "dummy", **self.valid_location})
        
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
        response = self.client.post(self.url, {"image": "dummy", **self.valid_location})
        
        self.assertEqual(response.status_code, 403)
        self.assertIn("does not match your authenticated account", response.data["error"])


# ---------------------------------------------------------------------------
# MyTeamView Tests
# ---------------------------------------------------------------------------

class MyTeamViewTests(APITestCase):
    """
    Full coverage of GET /api/attendance/my-team/

    Scenarios tested
    ----------------
    Authentication
      - Unauthenticated request is rejected (401)
      - Non-employee user (no employee profile) is rejected
    Team filtering
      - Same employment_type + section are included
      - Same employment_type but different section is excluded
      - Different employment_type but same section is excluded
      - Inactive employees are excluded
      - Subsection does NOT restrict results (A1 sees A2, A3, …)
    Status classification
      - CHECKED_IN: has a today check_in
      - CHECKED_IN: already checked OUT today is still CHECKED_IN (not YET_TO_CHECK_IN)
      - YET_TO_CHECK_IN: no attendance record today, not on leave
      - ON_LEAVE: has an APPROVED LeaveRequest covering today
      - Pending leave does NOT count as ON_LEAVE
      - Rejected/Cancelled leave does NOT count as ON_LEAVE
    Edge cases
      - Empty section → returns note, empty members list
      - Empty employment_type → returns note, empty members list
      - No team members → total_members = 0
      - Everyone checked in → yet_to_check_in_count = 0, on_leave_count = 0
      - Everyone on leave → on_leave_count = total_members
    Security
      - Response does NOT expose face_template / biometric fields
      - Response does NOT expose password / sensitive user fields
      - Employee cannot inject section/employment_type via query params
    Counts
      - checked_in_count, yet_to_check_in_count, on_leave_count are accurate
      - leave_type label is present in ON_LEAVE member data
    """

    URL = "/api/attendance/my-team/"

    def _make_user_and_employee(
        self,
        email,
        employment_type="INTERN",
        section="A",
        subsection="A1",
        is_active=True,
    ):
        User = get_user_model()
        user = User.objects.create_user(email=email, password="testpass123")
        emp = Employee.objects.create(
            user=user,
            department="Engineering",
            employment_type=employment_type,
            date_joined=date.today(),
            is_active=is_active,
            section=section,
            subsection=subsection,
        )
        return user, emp

    def _make_leave_type(self):
        from leave_management.models import LeaveType
        return LeaveType.objects.create(name="Casual Leave", code=f"CASUAL_{id(self)}")

    def _make_approved_leave(self, employee, leave_type, today):
        from leave_management.models import LeaveRequest
        return LeaveRequest.objects.create(
            employee=employee,
            leave_type=leave_type,
            start_date=today,
            end_date=today,
            day_type="FULL_DAY",
            duration_days=1,
            reason="Test leave",
            status="APPROVED",
        )

    def setUp(self):
        # The requesting employee: INTERN, section A, subsection A1
        self.user, self.me = self._make_user_and_employee(
            "me@example.com", employment_type="INTERN", section="A", subsection="A1"
        )
        self.today = timezone.localdate()
        self.leave_type = self._make_leave_type()

    # ------------------------------------------------------------------
    # Authentication tests
    # ------------------------------------------------------------------

    def test_unauthenticated_request_returns_401(self):
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 401)

    def test_non_employee_user_is_rejected(self):
        """A user with no Employee profile must be rejected."""
        User = get_user_model()
        admin_user = User.objects.create_user(email="admin@example.com", password="x", is_staff=True)
        self.client.force_authenticate(user=admin_user)
        response = self.client.get(self.URL)
        # IsEmployee permission blocks non-employees
        self.assertIn(response.status_code, [401, 403])

    # ------------------------------------------------------------------
    # Team filtering tests
    # ------------------------------------------------------------------

    def test_same_type_and_section_are_included(self):
        """Teammates with identical employment_type + section appear in results."""
        _, teammate = self._make_user_and_employee(
            "teammate@example.com", employment_type="INTERN", section="A", subsection="A2"
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        ids = [m["id"] for m in response.data["members"]]
        self.assertIn(self.me.id, ids)
        self.assertIn(teammate.id, ids)

    def test_different_section_is_excluded(self):
        """An INTERN in section B must not appear in section A's team."""
        _, other = self._make_user_and_employee(
            "other_section@example.com", employment_type="INTERN", section="B", subsection="B1"
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        ids = [m["id"] for m in response.data["members"]]
        self.assertNotIn(other.id, ids)

    def test_different_employment_type_is_excluded(self):
        """A PERMANENT employee in section A must not appear in INTERN section A's team."""
        _, other = self._make_user_and_employee(
            "permanent@example.com", employment_type="PERMANENT", section="A", subsection="A1"
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        ids = [m["id"] for m in response.data["members"]]
        self.assertNotIn(other.id, ids)

    def test_inactive_employee_is_excluded(self):
        """Inactive employees must never appear in results."""
        _, inactive = self._make_user_and_employee(
            "inactive@example.com", employment_type="INTERN", section="A", subsection="A1", is_active=False
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        ids = [m["id"] for m in response.data["members"]]
        self.assertNotIn(inactive.id, ids)

    def test_subsection_does_not_restrict_results(self):
        """A1, A2, A3 subsections must all appear when querying section A."""
        _, a2 = self._make_user_and_employee(
            "a2@example.com", employment_type="INTERN", section="A", subsection="A2"
        )
        _, a3 = self._make_user_and_employee(
            "a3@example.com", employment_type="INTERN", section="A", subsection="A3"
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        ids = [m["id"] for m in response.data["members"]]
        self.assertIn(self.me.id, ids)
        self.assertIn(a2.id, ids)
        self.assertIn(a3.id, ids)

    # ------------------------------------------------------------------
    # Status classification tests
    # ------------------------------------------------------------------

    def test_checked_in_classification(self):
        """Employee with today's check_in → CHECKED_IN."""
        Attendance.objects.create(
            employee=self.me,
            date=self.today,
            check_in=timezone.now(),
            status="INCOMPLETE",
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        me_data = next(m for m in response.data["members"] if m["id"] == self.me.id)
        self.assertEqual(me_data["status"], "CHECKED_IN")
        self.assertEqual(response.data["checked_in_count"], 1)
        self.assertIsNotNone(me_data["check_in_time"])

    def test_checked_out_employee_stays_in_checked_in(self):
        """
        An employee who has already checked OUT today must still be classified
        as CHECKED_IN (not YET_TO_CHECK_IN), because they were present.
        """
        check_in = timezone.now() - timedelta(hours=8)
        check_out = timezone.now()
        Attendance.objects.create(
            employee=self.me,
            date=self.today,
            check_in=check_in,
            check_out=check_out,
            status="PRESENT",
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        me_data = next(m for m in response.data["members"] if m["id"] == self.me.id)
        self.assertEqual(me_data["status"], "CHECKED_IN")
        self.assertIsNotNone(me_data["check_out_time"])

    def test_yet_to_check_in_classification(self):
        """Employee with no attendance record and no leave → YET_TO_CHECK_IN."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        me_data = next(m for m in response.data["members"] if m["id"] == self.me.id)
        self.assertEqual(me_data["status"], "YET_TO_CHECK_IN")
        self.assertEqual(response.data["yet_to_check_in_count"], 1)
        self.assertIsNone(me_data["check_in_time"])

    def test_approved_leave_classification(self):
        """Employee with APPROVED leave covering today → ON_LEAVE."""
        self._make_approved_leave(self.me, self.leave_type, self.today)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        me_data = next(m for m in response.data["members"] if m["id"] == self.me.id)
        self.assertEqual(me_data["status"], "ON_LEAVE")
        self.assertEqual(response.data["on_leave_count"], 1)
        self.assertEqual(me_data["leave_type"], "Casual Leave")

    def test_pending_leave_not_on_leave(self):
        """PENDING leave must NOT classify the employee as ON_LEAVE."""
        from leave_management.models import LeaveRequest
        LeaveRequest.objects.create(
            employee=self.me,
            leave_type=self.leave_type,
            start_date=self.today,
            end_date=self.today,
            day_type="FULL_DAY",
            duration_days=1,
            reason="Pending",
            status="PENDING",
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        me_data = next(m for m in response.data["members"] if m["id"] == self.me.id)
        self.assertNotEqual(me_data["status"], "ON_LEAVE")
        self.assertEqual(response.data["on_leave_count"], 0)

    def test_rejected_leave_not_on_leave(self):
        """DENIED leave must NOT classify the employee as ON_LEAVE."""
        from leave_management.models import LeaveRequest
        LeaveRequest.objects.create(
            employee=self.me,
            leave_type=self.leave_type,
            start_date=self.today,
            end_date=self.today,
            day_type="FULL_DAY",
            duration_days=1,
            reason="Denied",
            status="DENIED",
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        me_data = next(m for m in response.data["members"] if m["id"] == self.me.id)
        self.assertNotEqual(me_data["status"], "ON_LEAVE")

    def test_cancelled_leave_not_on_leave(self):
        """CANCELLED leave must NOT classify the employee as ON_LEAVE."""
        from leave_management.models import LeaveRequest
        LeaveRequest.objects.create(
            employee=self.me,
            leave_type=self.leave_type,
            start_date=self.today,
            end_date=self.today,
            day_type="FULL_DAY",
            duration_days=1,
            reason="Cancelled",
            status="CANCELLED",
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        me_data = next(m for m in response.data["members"] if m["id"] == self.me.id)
        self.assertNotEqual(me_data["status"], "ON_LEAVE")

    # ------------------------------------------------------------------
    # Count accuracy tests
    # ------------------------------------------------------------------

    def test_counts_are_accurate(self):
        """checked_in, yet_to_check_in, on_leave counts match actual data."""
        # me → ON_LEAVE
        self._make_approved_leave(self.me, self.leave_type, self.today)

        # teammate1 → CHECKED_IN
        _, t1 = self._make_user_and_employee("t1@example.com", employment_type="INTERN", section="A", subsection="A2")
        Attendance.objects.create(employee=t1, date=self.today, check_in=timezone.now(), status="INCOMPLETE")

        # teammate2 → YET_TO_CHECK_IN
        _, t2 = self._make_user_and_employee("t2@example.com", employment_type="INTERN", section="A", subsection="A3")

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_members"], 3)
        self.assertEqual(response.data["checked_in_count"], 1)
        self.assertEqual(response.data["yet_to_check_in_count"], 1)
        self.assertEqual(response.data["on_leave_count"], 1)

    # ------------------------------------------------------------------
    # Edge case tests
    # ------------------------------------------------------------------

    def test_empty_section_returns_graceful_response(self):
        """Employee with no section set gets a graceful empty response."""
        self.me.section = ""
        self.me.save()
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_members"], 0)
        self.assertIn("note", response.data)

    def test_empty_employment_type_returns_graceful_response(self):
        """Employee with no employment_type gets a graceful empty response."""
        # employment_type has choices but CharField allows blank at DB level
        Employee.objects.filter(pk=self.me.pk).update(employment_type="")
        self.me.refresh_from_db()
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_members"], 0)
        self.assertIn("note", response.data)

    def test_no_team_members_returns_empty_list(self):
        """Single employee in a unique type+section: only themselves, no errors."""
        self.me.employment_type = "CONTRACT"
        self.me.section = "UNIQUE"
        self.me.save()
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        # Only me
        self.assertEqual(response.data["total_members"], 1)
        self.assertEqual(response.data["members"][0]["id"], self.me.id)

    def test_everyone_checked_in(self):
        """All members checked in → yet_to_check_in_count=0, on_leave_count=0."""
        _, t1 = self._make_user_and_employee("t1b@example.com", employment_type="INTERN", section="A", subsection="A2")
        for emp in [self.me, t1]:
            Attendance.objects.create(employee=emp, date=self.today, check_in=timezone.now(), status="INCOMPLETE")
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["yet_to_check_in_count"], 0)
        self.assertEqual(response.data["on_leave_count"], 0)
        self.assertEqual(response.data["checked_in_count"], 2)

    def test_everyone_on_leave(self):
        """All members on leave → on_leave_count=total_members, others=0."""
        _, t1 = self._make_user_and_employee("t1c@example.com", employment_type="INTERN", section="A", subsection="A2")
        for emp in [self.me, t1]:
            self._make_approved_leave(emp, self.leave_type, self.today)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["on_leave_count"], 2)
        self.assertEqual(response.data["checked_in_count"], 0)
        self.assertEqual(response.data["yet_to_check_in_count"], 0)

    # ------------------------------------------------------------------
    # Security tests
    # ------------------------------------------------------------------

    def test_face_biometric_fields_not_exposed(self):
        """face_template or any biometric field must never appear in the response."""
        from employees.models import FaceProfile
        FaceProfile.objects.create(
            employee=self.me,
            face_template=[0.1] * 512,
            status="ACTIVE",
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        raw_response = str(response.data)
        self.assertNotIn("face_template", raw_response)
        self.assertNotIn("face_profile", raw_response)
        # Spot check each member dict too
        for member in response.data["members"]:
            self.assertNotIn("face_template", member)

    def test_password_not_exposed(self):
        """password field must never appear in the response."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        raw_response = str(response.data)
        self.assertNotIn("password", raw_response)

    def test_query_params_cannot_override_team(self):
        """
        Passing section/employment_type/employee_id as query params must have
        zero effect — the team is always derived from the authenticated user.
        """
        _, other = self._make_user_and_employee(
            "other_inject@example.com", employment_type="PERMANENT", section="B", subsection="B1"
        )
        self.client.force_authenticate(user=self.user)
        # Attempt to inject a different section/type
        response = self.client.get(self.URL + "?section=B&employment_type=PERMANENT")
        self.assertEqual(response.status_code, 200)
        # Should still see INTERN / section A (me), NOT section B PERMANENT
        self.assertEqual(response.data["team_employment_type"], "INTERN")
        self.assertEqual(response.data["team_section"], "A")
        ids = [m["id"] for m in response.data["members"]]
        self.assertNotIn(other.id, ids)

    def test_response_includes_required_fields(self):
        """Top-level response shape is complete and correct."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        for key in [
            "team_employment_type",
            "team_section",
            "total_members",
            "checked_in_count",
            "yet_to_check_in_count",
            "on_leave_count",
            "members",
        ]:
            self.assertIn(key, response.data)

    def test_member_fields_are_correct(self):
        """Each member dict contains id, name, department, subsection, status, check_in_time, check_out_time."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["members"]), 1)
        member = response.data["members"][0]
        for key in ["id", "name", "department", "subsection", "status", "check_in_time", "check_out_time"]:
            self.assertIn(key, member)

    def test_on_leave_member_has_leave_type_field(self):
        """ON_LEAVE members must include a leave_type label."""
        self._make_approved_leave(self.me, self.leave_type, self.today)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        me_data = next(m for m in response.data["members"] if m["id"] == self.me.id)
        self.assertIn("leave_type", me_data)
        self.assertEqual(me_data["leave_type"], "Casual Leave")

    def test_team_metadata_in_response(self):
        """team_employment_type and team_section in response match the authenticated employee."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["team_employment_type"], "INTERN")
        self.assertEqual(response.data["team_section"], "A")

