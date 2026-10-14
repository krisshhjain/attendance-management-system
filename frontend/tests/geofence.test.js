import { test, expect } from "vitest";
import {
  ATTENDANCE_GEOFENCE,
  calculateHaversineDistance,
  isLocationInsideGeofence,
} from "../src/lib/geofence.js";

test("calculates known distances and uses the configured office radius", () => {
  expect(calculateHaversineDistance(0, 0, 0, 0)).toBe(0);
  expect(calculateHaversineDistance(0, 0, 0, 1)).toBeGreaterThan(111_000);
  expect(
    isLocationInsideGeofence(ATTENDANCE_GEOFENCE.latitude, ATTENDANCE_GEOFENCE.longitude),
  ).toBe(true);
  expect(isLocationInsideGeofence(0, 0)).toBe(false);
});

test("uses active office locations and falls back when none are active", () => {
  const coordinates = { latitude: 12, longitude: 34 };
  expect(isLocationInsideGeofence(12, 34, [{ ...coordinates, radius_meters: 50 }])).toBe(true);
  expect(isLocationInsideGeofence(12, 34, [{ ...coordinates, is_active: false }])).toBe(false);
  expect(isLocationInsideGeofence(12, 34, [{ ...coordinates, radius_meters: 5 }])).toBe(true);
  expect(isLocationInsideGeofence(12, 34.01, [{ ...coordinates, radius_meters: 5 }])).toBe(false);
});
