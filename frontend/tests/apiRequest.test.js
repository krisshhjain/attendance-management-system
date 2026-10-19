import { test, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "./mocks/server.js";
import { API_BASE_URL, ApiError, apiRequest, tokenStore } from "../src/lib/api.js";

test("sends bearer auth and JSON payloads and returns parsed responses", async () => {
  tokenStore.set("access-token");
  let received;
  server.use(
    http.post(`${API_BASE_URL}/private/`, async ({ request }) => {
      received = {
        authorization: request.headers.get("authorization"),
        body: await request.json(),
      };
      return HttpResponse.json({ saved: true });
    }),
  );

  await expect(
    apiRequest("/private/", { method: "POST", body: { enabled: true } }),
  ).resolves.toEqual({ saved: true });
  expect(received).toEqual({ authorization: "Bearer access-token", body: { enabled: true } });
});

test("refreshes an expired access token and retries the original request", async () => {
  tokenStore.set("expired-token", "refresh-token");
  let attempts = 0;
  server.use(
    http.get(`${API_BASE_URL}/private/`, ({ request }) => {
      attempts += 1;
      if (request.headers.get("authorization") === "Bearer expired-token") {
        return HttpResponse.json({ detail: "expired" }, { status: 401 });
      }
      return HttpResponse.json({ value: "fresh" });
    }),
    http.post(`${API_BASE_URL}/auth/token/refresh/`, async ({ request }) => {
      expect(await request.json()).toEqual({ refresh: "refresh-token" });
      return HttpResponse.json({ access: "fresh-token" });
    }),
  );

  await expect(apiRequest("/private/")).resolves.toEqual({ value: "fresh" });
  expect(attempts).toBe(2);
  expect(tokenStore.access).toBe("fresh-token");
});

test("clears invalid sessions and returns a friendly unauthorized error", async () => {
  tokenStore.set("expired-token", "invalid-refresh");
  server.use(
    http.get(`${API_BASE_URL}/private/`, () => new HttpResponse(null, { status: 401 })),
    http.post(`${API_BASE_URL}/auth/token/refresh/`, () => HttpResponse.json({}, { status: 401 })),
  );

  let error;
  try {
    await apiRequest("/private/");
  } catch (caught) {
    error = caught;
  }
  expect(error).toBeInstanceOf(ApiError);
  expect(error.status).toBe(401);
  expect(error.message).toBe("Your session has expired. Please sign in again.");
  expect(tokenStore.access).toBeNull();
  expect(tokenStore.refresh).toBeNull();
});

test("does not add authorization for public requests and reports network failures", async () => {
  let authorization;
  server.use(
    http.get(`${API_BASE_URL}/public/`, ({ request }) => {
      authorization = request.headers.get("authorization");
      return HttpResponse.json({ public: true });
    }),
    http.get(`${API_BASE_URL}/offline/`, () => HttpResponse.error()),
  );
  tokenStore.set("access-token");

  await expect(apiRequest("/public/", { auth: false })).resolves.toEqual({ public: true });
  expect(authorization).toBeNull();
  await expect(apiRequest("/offline/")).rejects.toMatchObject({
    status: 0,
    message: expect.stringContaining("Unable to reach"),
  });
});
