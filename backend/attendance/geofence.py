"""
Attendance Geofence Configuration & Utilities (MVP).

Centralized configuration for the workplace geofence coordinates and radius.
This file can later be replaced or extended with database-driven geofences.
"""

import math
import os

# Workplace geofence constants loaded from environment variables
WORKPLACE_LATITUDE = float(os.getenv("GEOFENCE_LATITUDE", "28.53004839800301"))
WORKPLACE_LONGITUDE = float(os.getenv("GEOFENCE_LONGITUDE", "77.34971793979841"))
GEOFENCE_RADIUS_METERS = float(os.getenv("GEOFENCE_RADIUS_METERS", "150.0"))
MAX_ACCURACY_METERS = float(os.getenv("GEOFENCE_MAX_ACCURACY_METERS", "200.0"))


def calculate_haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculates the great-circle distance between two points in meters
    using the Haversine formula.
    """
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def validate_attendance_geofence(latitude, longitude, accuracy):
    """
    Validates device coordinates against dynamically configured workplace office locations.

    Returns:
        (is_valid: bool, error_message: str | None, distance: float | None, parsed_coords: tuple | None)
    """
    if latitude is None or longitude is None:
        return (
            False,
            "Location coordinates (latitude and longitude) are required.",
            None,
            None,
        )

    try:
        lat = float(latitude)
        lon = float(longitude)
    except (ValueError, TypeError):
        return False, "Invalid location coordinates provided.", None, None

    try:
        acc = float(accuracy) if accuracy is not None else 0.0
    except (ValueError, TypeError):
        return False, "Invalid location accuracy provided.", None, None

    # Accuracy check: If GPS accuracy is worse than 200 meters, reject it
    if acc > MAX_ACCURACY_METERS:
        return (
            False,
            "Your location accuracy is too low. Please enable precise location and try again.",
            None,
            (lat, lon, acc),
        )

    # Fetch active office locations dynamically from DB
    try:
        from .models import OfficeLocation
        locations = list(OfficeLocation.objects.filter(is_active=True))
    except Exception:
        locations = []

    if locations:
        best_distance = float("inf")
        nearest_location = None
        for loc in locations:
            dist = calculate_haversine_distance(lat, lon, loc.latitude, loc.longitude)
            if dist <= loc.radius_meters:
                print(f"[GEOFENCE DEBUG] Matched Office: {loc.name}, Distance: {dist:.1f}m <= Radius: {loc.radius_meters}m")
                return True, None, dist, (lat, lon, acc)
            if dist < best_distance:
                best_distance = dist
                nearest_location = loc

        print(f"[GEOFENCE DEBUG] Outside all offices. Nearest: {nearest_location.name} ({best_distance:.1f}m)")
        return (
            False,
            f"You are outside the allowed attendance area. Nearest location: {nearest_location.name} ({best_distance:.1f}m away, allowed: {nearest_location.radius_meters}m). Please move closer to the workplace and try again.",
            best_distance,
            (lat, lon, acc),
        )
    else:
        # Fallback to default constants if DB table is empty
        distance = calculate_haversine_distance(
            lat, lon, WORKPLACE_LATITUDE, WORKPLACE_LONGITUDE
        )
        print(f"[GEOFENCE DEBUG] Fallback Distance: {distance}m, Radius: {GEOFENCE_RADIUS_METERS}m, Pass: {distance <= GEOFENCE_RADIUS_METERS}")
        if distance > GEOFENCE_RADIUS_METERS:
            return (
                False,
                f"You are outside the allowed attendance area. Distance: {distance:.1f}m, Allowed: {GEOFENCE_RADIUS_METERS}m. Please move closer to the workplace and try again.",
                distance,
                (lat, lon, acc),
            )
        return True, None, distance, (lat, lon, acc)

