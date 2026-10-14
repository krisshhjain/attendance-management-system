import { test, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server.js";
import { API_BASE_URL } from "../src/lib/api.js";
import {
  checkIn,
  checkOut,
  editAdminAttendance,
  forceAdminCheckout,
  getAdminAttendance,
  getHistory,
  getToday,
  resetAdminAttendance,
} from "../src/lib/attendance.js";

test("loads today's and admin attendance using the requested date", async () => {
  const requests = [];
  server.use(
    http.get(`${API_BASE_URL}/attendance/today/`, ({ request }) => {
      requests.push(request.url);
      return HttpResponse.json({ status: "CHECKED_IN" });
    }),
    http.get(`${API_BASE_URL}/admin/attendance/`, ({ request }) => {
      requests.push(request.url);
      return HttpResponse.json([]);
    }),
  );

  await expect(getToday()).resolves.toEqual({ status: "CHECKED_IN" });
  await expect(getAdminAttendance("2026-01-26")).resolves.toEqual([]);
  expect(requests).toEqual([
    `${API_BASE_URL}/attendance/today/`,
    `${API_BASE_URL}/admin/attendance/?date=2026-01-26`,
  ]);
});

test("normalizes history API responses without hiding valid array records", async () => {
  let payload = [{ id: 1 }];
  server.use(http.get(`${API_BASE_URL}/attendance/history/`, () => HttpResponse.json(payload)));

  await expect(getHistory()).resolves.toEqual([{ id: 1 }]);
  payload = { results: [{ id: 2 }] };
  await expect(getHistory()).resolves.toEqual([{ id: 2 }]);
  payload = { count: 0 };
  await expect(getHistory()).resolves.toEqual([]);
});

test("sends coordinates and admin mutation payloads to their API routes", async () => {
  const requests = [];
  server.use(
    http.post(`${API_BASE_URL}/*`, async ({ request }) => {
      requests.push({ url: new URL(request.url).pathname, body: await request.json() });
      return HttpResponse.json({ ok: true });
    }),
  );
  const coordinates = { latitude: 10, longitude: 20 };

  await checkIn(coordinates);
  await checkOut(coordinates);
  await forceAdminCheckout({ all: true, date: "2026-01-26" });
  await resetAdminAttendance({ employee: "a@example.test", reason: "Correction" });
  await editAdminAttendance({ employee: "a@example.test", status: "PRESENT" });

  expect(requests).toEqual([
    { url: "/api/attendance/check-in/", body: coordinates },
    { url: "/api/attendance/check-out/", body: coordinates },
    { url: "/api/admin/force-checkout/", body: { all: true, date: "2026-01-26" } },
    {
      url: "/api/admin/attendance/reset/",
      body: { employee: "a@example.test", reason: "Correction" },
    },
    { url: "/api/admin/attendance/edit/", body: { employee: "a@example.test", status: "PRESENT" } },
  ]);
});
