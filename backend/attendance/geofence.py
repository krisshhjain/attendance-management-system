"""
Attendance Geofence Configuration & Utilities (MVP).

Centralized configuration for the workplace geofence coordinates and radius.
This file can later be replaced or extended with database-driven geofences.
"""

import math

# Workplace geofence constants (MVP)
ATTENDANCE_GEOFENCE = {
    "latitude": 28.5300409164614,
    "longitude": 77.34955699676016,
    "radius_meters": 150.0,
    "max_accuracy_meters": 200.0,
}

WORKPLACE_LATITUDE = ATTENDANCE_GEOFENCE["latitude"]
WORKPLACE_LONGITUDE = ATTENDANCE_GEOFENCE["longitude"]
GEOFENCE_RADIUS_METERS = ATTENDANCE_GEOFENCE["radius_meters"]
MAX_ACCURACY_METERS = ATTENDANCE_GEOFENCE["max_accuracy_meters"]


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
    Validates device coordinates against the workplace geofence.

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

    # Distance calculation
    distance = calculate_haversine_distance(
        lat, lon, WORKPLACE_LATITUDE, WORKPLACE_LONGITUDE
    )

    # Radius check: If distance is > 150 meters, reject it
    if distance > GEOFENCE_RADIUS_METERS:
        return (
            False,
            "You are outside the allowed attendance area. Please move closer to the workplace and try again.",
            distance,
            (lat, lon, acc),
        )

    return True, None, distance, (lat, lon, acc)
