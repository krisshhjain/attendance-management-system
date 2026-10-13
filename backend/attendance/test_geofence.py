from django.test import TestCase
from rest_framework.exceptions import ValidationError

from .geofence import validate_attendance_geofence
from .models import OfficeLocation
from .serializers import OfficeLocationSerializer


class DynamicGeofenceTests(TestCase):
    def test_inside_any_active_office_accepts_and_returns_nearest_match(self):
        OfficeLocation.objects.create(
            name="Remote office", latitude=12.0, longitude=77.0,
            radius_meters=20,
        )
        OfficeLocation.objects.create(
            name="Current office", latitude=12.001, longitude=77.0,
            radius_meters=200,
        )

        valid, error, distance, coords = validate_attendance_geofence(
            "12.001", "77.0", "8"
        )

        self.assertTrue(valid)
        self.assertIsNone(error)
        self.assertAlmostEqual(distance, 0)
        self.assertEqual(coords, (12.001, 77.0, 8.0))

    def test_outside_offices_reports_the_nearest_allowed_location(self):
        OfficeLocation.objects.create(
            name="A close office", latitude=0.001, longitude=0.0,
            radius_meters=50,
        )
        OfficeLocation.objects.create(
            name="Z far office", latitude=1.0, longitude=1.0,
            radius_meters=50,
        )

        valid, error, distance, coords = validate_attendance_geofence(
            0, 0, 5
        )

        self.assertFalse(valid)
        self.assertIn("A close office", error)
        self.assertGreater(distance, 50)
        self.assertEqual(coords, (0.0, 0.0, 5.0))

    def test_office_location_serializer_rejects_invalid_coordinates_and_name(self):
        invalid_latitude = OfficeLocationSerializer(data={
            "name": "Test office", "latitude": 91,
            "longitude": 0, "radius_meters": 100,
        })
        invalid_longitude = OfficeLocationSerializer(data={
            "name": "Test office", "latitude": 0,
            "longitude": 181, "radius_meters": 100,
        })
        empty_name = OfficeLocationSerializer(data={
            "name": "   ", "latitude": 0,
            "longitude": 0, "radius_meters": 100,
        })
        valid_location = OfficeLocationSerializer(data={
            "name": " Valid office ", "latitude": 90,
            "longitude": -180, "radius_meters": 100,
        })

        self.assertFalse(invalid_latitude.is_valid())
        self.assertIn("-90 and 90", str(invalid_latitude.errors["latitude"]))
        self.assertFalse(invalid_longitude.is_valid())
        self.assertIn("-180 and 180", str(invalid_longitude.errors["longitude"]))
        self.assertFalse(empty_name.is_valid())
        self.assertIn("may not be blank", str(empty_name.errors["name"]))
        with self.assertRaises(ValidationError) as error:
            empty_name.validate_name(None)
        self.assertIn("cannot be empty", str(error.exception))
        self.assertTrue(valid_location.is_valid(), valid_location.errors)
        self.assertEqual(valid_location.validated_data["name"], "Valid office")
