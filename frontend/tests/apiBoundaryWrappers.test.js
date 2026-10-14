import { test, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server.js";
import { API_BASE_URL, downloadSystemLogs, tokenStore, uploadFile } from "../src/lib/api.js";
import * as api from "../src/lib/api.js";

test("builds leave, shift, regularization, location and system-log API requests", async () => {
  const requests = [];
  server.use(
    http.get(`${API_BASE_URL}/*`, async ({ request }) => {
      requests.push({
        method: request.method,
        url: request.url,
        body: await request
          .clone()
          .json()
          .catch(() => null),
      });
      return HttpResponse.json({ ok: true });
    }),
    http.post(`${API_BASE_URL}/*`, async ({ request }) => {
      requests.push({
        method: request.method,
        url: request.url,
        body: await request
          .clone()
          .json()
          .catch(() => null),
      });
      return HttpResponse.json({ ok: true });
    }),
    http.patch(`${API_BASE_URL}/*`, async ({ request }) => {
      requests.push({
        method: request.method,
        url: request.url,
        body: await request
          .clone()
          .json()
          .catch(() => null),
      });
      return HttpResponse.json({ ok: true });
    }),
    http.put(`${API_BASE_URL}/*`, async ({ request }) => {
      requests.push({
        method: request.method,
        url: request.url,
        body: await request
          .clone()
          .json()
          .catch(() => null),
      });
      return HttpResponse.json({ ok: true });
    }),
    http.delete(`${API_BASE_URL}/*`, async ({ request }) => {
      requests.push({ method: request.method, url: request.url, body: null });
      return HttpResponse.json({ ok: true });
    }),
  );
  const sample = { reason: "Testing request contract" };

  await api.fetchLeaveTypes();
  await api.fetchLeaveBalances(2026);
  await api.fetchLeaveRequests("PENDING");
  await api.submitLeaveRequest(sample);
  await api.cancelLeaveRequest(2);
  await api.estimateLeaveDuration("2026-01-01", "2026-01-02", "HALF_DAY");
  await api.fetchAdminLeaveRequests({ status: "PENDING", section_id: 4 });
  await api.approveLeaveRequest(3, "Approved");
  await api.denyLeaveRequest(4, "Insufficient balance");
  await api.cancelApprovedLeaveRequest(5);
  await api.fetchAdminLeaveBalances({ year: 2026 });
  await api.fetchLeaveTypesAll();
  await api.createLeaveType(sample);
  await api.updateLeaveType(6, sample);
  await api.deleteLeaveType(7);
  await api.fetchLeavePoliciesAll();
  await api.createLeavePolicy(sample);
  await api.updateLeavePolicy(8, sample);
  await api.deleteLeavePolicy(9);
  await api.fetchMyShift();
  await api.fetchActiveShifts();
  await api.selfAssignShift(12);
  await api.fetchAdminShiftConfiguration();
  await api.configureEmploymentTypeShifts("FULL_TIME", [{ id: 12 }]);
  await api.fetchAllShifts();
  await api.fetchMyRegularizationRequests({ status: "PENDING", page: 2 });
  await api.fetchMyRegularizationQuota();
  await api.createRegularizationRequest(sample);
  await api.fetchAdminRegularizationRequests({ status: "PENDING" });
  await api.fetchAdminRegularizationQuotaPolicy();
  await api.updateAdminRegularizationQuotaPolicy(sample);
  await api.fetchAdminRegularizationRequest(10);
  await api.approveRegularizationRequest(10, sample);
  await api.rejectRegularizationRequest(11, "Missing details");
  await api.fetchOfficeLocations();
  await api.createOfficeLocation(sample);
  await api.updateOfficeLocation(12, sample);
  await api.deleteOfficeLocation(12);
  await api.fetchSystemLogs({ severity: "ERROR", page: 2, empty: "" });
  await api.fetchSystemLogActors("ann");
  await api.deleteSystemLogs("2026-01-01");

  const requestFor = (path, method = "GET") =>
    requests.find((request) => new URL(request.url).pathname === path && request.method === method);
  expect(requestFor("/api/leave/balances/").url).toContain("year=2026");
  expect(requestFor("/api/leave/requests/").url).toContain("status=PENDING");
  expect(requestFor("/api/leave/estimate-duration/", "POST").body).toEqual({
    start_date: "2026-01-01",
    end_date: "2026-01-02",
    day_type: "HALF_DAY",
  });
  expect(requestFor("/api/leave/admin/requests/", "GET").url).toContain("section_id=4");
  expect(requestFor("/api/leave/admin/requests/3/approve/", "POST").body).toEqual({
    remarks: "Approved",
  });
  expect(requestFor("/api/attendance/my-shift/assign/", "POST").body).toEqual({ shift_id: 12 });
  expect(requestFor("/api/attendance/admin/shift/configure/", "POST").body).toEqual({
    employment_type: "FULL_TIME",
    shifts: [{ id: 12 }],
  });
  expect(requestFor("/api/attendance/regularization/list/").url).toContain("page=2");
  expect(requestFor("/api/attendance/admin/regularization/11/reject/", "POST").body).toEqual({
    rejection_reason: "Missing details",
  });
  expect(requestFor("/api/attendance/locations/12/", "PUT").body).toEqual(sample);
  expect(requestFor("/api/system-logs/").url).toContain("severity=ERROR");
  expect(requestFor("/api/system-logs/actors/").url).toContain("search=ann");
  expect(requestFor("/api/system-logs/", "DELETE").url).toContain("until_date=2026-01-01");
});

test("uploads leave attachments as multipart data with the active access token", async () => {
  tokenStore.set("upload-token");
  let received;
  server.use(
    http.post(`${API_BASE_URL}/leave/upload/`, async ({ request }) => {
      received = {
        authorization: request.headers.get("authorization"),
        contentType: request.headers.get("content-type"),
      };
      return HttpResponse.json({ url: "/media/proof.txt" });
    }),
  );
  const file = new File(["supporting document"], "proof.txt", { type: "text/plain" });

  await expect(uploadFile(file)).resolves.toEqual({ url: "/media/proof.txt" });
  expect(received.authorization).toBe("Bearer upload-token");
  expect(received.contentType).toContain("multipart/form-data");
});

test("downloads system logs with a format-specific filename and auth header", async () => {
  tokenStore.set("download-token");
  let authorization;
  let requestedUrl;
  server.use(
    http.get(`${API_BASE_URL}/system-logs/export/`, ({ request }) => {
      authorization = request.headers.get("authorization");
      requestedUrl = request.url;
      return new HttpResponse("id,event\n1,LOGIN", { headers: { "Content-Type": "text/csv" } });
    }),
  );

  const download = await downloadSystemLogs({ status: "FAILED" }, "xlsx");
  expect(authorization).toBe("Bearer download-token");
  expect(requestedUrl).toContain("status=FAILED");
  expect(requestedUrl).toContain("export_format=xlsx");
  expect(download.filename).toBe("system-logs.xlsx");
  await expect(download.blob.text()).resolves.toContain("LOGIN");
});
