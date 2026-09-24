from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from employees.models import Employee
from attendance.models import Attendance
from attendance.geofence import (
    WORKPLACE_LATITUDE,
    WORKPLACE_LONGITUDE,
    GEOFENCE_RADIUS_METERS,
    MAX_ACCURACY_METERS,
    calculate_haversine_distance,
)

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

        # Point ~500m north of workplace
        self.outside_location = {
            "latitude": WORKPLACE_LATITUDE + 0.005,
            "longitude": WORKPLACE_LONGITUDE,
            "accuracy": 10.0,
        }

        # Poor accuracy
        self.low_accuracy_location = {
            "latitude": WORKPLACE_LATITUDE,
            "longitude": WORKPLACE_LONGITUDE,
            "accuracy": 250.0,
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
        self.assertGreater(dist_outside, GEOFENCE_RADIUS_METERS)

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
        self.assertEqual(
            response.data["error"],
            "You are outside the allowed attendance area. Please move closer to the workplace and try again."
        )
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
        self.assertEqual(
            response.data["error"],
            "You are outside the allowed attendance area. Please move closer to the workplace and try again."
        )
