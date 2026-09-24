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
