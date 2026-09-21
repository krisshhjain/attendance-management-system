import { apiRequest } from "./api.js";

export function getToday() {
  return apiRequest("/attendance/today/");
}

export function getAdminAttendance(date) {
  const qs = date ? `?date=${date}` : "";
  return apiRequest(`/admin/attendance/${qs}`);
}


export function checkIn() {
  return apiRequest("/attendance/check-in/", { method: "POST" });
}

export function checkOut() {
  return apiRequest("/attendance/check-out/", { method: "POST" });
}

export async function getHistory() {
  const data = await apiRequest("/attendance/history/");
  if (Array.isArray(data)) return data;
  return data?.results ?? [];
}

export function forceAdminCheckout(payload) {
  return apiRequest("/admin/force-checkout/", {
    method: "POST",
    body: payload,
  });
}
