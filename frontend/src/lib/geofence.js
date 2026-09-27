/**
 * Workplace Attendance Geofence Configuration (MVP)
 *
 * Centralized constant for the workplace location and geofence parameters.
 * Note: Validation is strictly enforced by the backend; these constants are
 * kept here for UI reference and future offline/pre-check features.
 */
export const ATTENDANCE_GEOFENCE = {
  latitude: 28.5300409164614,
  longitude: 77.34955699676016,
  radiusMeters: 150,
  maxAccuracyMeters: 200,
};

export function calculateHaversineDistance(lat1, lon1, lat2, lon2) {
  const R = 6371000.0;
  const phi1 = (lat1 * Math.PI) / 180;
  const phi2 = (lat2 * Math.PI) / 180;
  const deltaPhi = ((lat2 - lat1) * Math.PI) / 180;
  const deltaLambda = ((lon2 - lon1) * Math.PI) / 180;

  const a =
    Math.sin(deltaPhi / 2.0) ** 2 +
    Math.cos(phi1) * Math.cos(phi2) * Math.sin(deltaLambda / 2.0) ** 2;
  const c = 2.0 * Math.atan2(Math.sqrt(a), Math.sqrt(1.0 - a));
  return R * c;
}

export function isLocationInsideGeofence(latitude, longitude, officeLocations = []) {
  if (Array.isArray(officeLocations) && officeLocations.length > 0) {
    const activeLocations = officeLocations.filter((loc) => loc.is_active !== false);
    if (activeLocations.length > 0) {
      return activeLocations.some((loc) => {
        const dist = calculateHaversineDistance(latitude, longitude, loc.latitude, loc.longitude);
        const radius = loc.radius_meters || ATTENDANCE_GEOFENCE.radiusMeters;
        return dist <= radius;
      });
    }
  }

  const distance = calculateHaversineDistance(
    latitude,
    longitude,
    ATTENDANCE_GEOFENCE.latitude,
    ATTENDANCE_GEOFENCE.longitude,
  );
  return distance <= ATTENDANCE_GEOFENCE.radiusMeters;
}


