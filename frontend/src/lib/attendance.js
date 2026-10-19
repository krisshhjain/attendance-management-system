/**
 * lib/attendance.js — Attendance API wrapper functions.
 *
 * Thin wrappers over apiRequest that map to specific backend attendance
 * endpoints. Admin-only operations (force checkout, reset, edit) use the
 * /admin/ prefix and require is_superuser or is_staff on the server side.
 */
import { apiRequest } from "./api.js";

export function getToday() {
  return apiRequest("/attendance/today/");
}

export function getAdminAttendance(date) {
  const qs = date ? `?date=${date}` : "";
  return apiRequest(`/admin/attendance/${qs}`);
}

export function checkIn(locationData) {
  return apiRequest("/attendance/check-in/", {
    method: "POST",
    body: locationData,
  });
}

export function checkOut(locationData) {
  return apiRequest("/attendance/check-out/", {
    method: "POST",
    body: locationData,
  });
}

export async function getHistory() {
  const data = await apiRequest("/attendance/history/");
  // The history endpoint may return either a plain array (legacy) or a
  // DRF paginated object { count, results: [] }. Both are normalised here
  // so consumers always receive an array without handling both shapes.
  if (Array.isArray(data)) return data;
  return data?.results ?? [];
}

export function forceAdminCheckout(payload) {
  return apiRequest("/admin/force-checkout/", {
    method: "POST",
    body: payload,
  });
}

export function resetAdminAttendance(payload) {
  return apiRequest("/admin/attendance/reset/", {
    method: "POST",
    body: payload,
  });
}

export function editAdminAttendance(payload) {
  return apiRequest("/admin/attendance/edit/", {
    method: "POST",
    body: payload,
  });
}
