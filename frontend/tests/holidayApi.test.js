import assert from "node:assert/strict";
import test from "node:test";
import { createHoliday, fetchActiveHolidays, fetchAdminHolidays, updateHoliday } from "../src/lib/api.js";

test("holiday read and SuperUser management API helpers use the backend endpoints", async () => {
  const originalFetch = globalThis.fetch;
  const calls = [];
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url: String(url), options });
    return new Response("[]", { status: 200, headers: { "Content-Type": "application/json" } });
  };
  try {
    await fetchActiveHolidays();
    await fetchAdminHolidays();
    await createHoliday({ date: "2026-01-26", name: "Republic Day" });
    await updateHoliday(7, { is_active: false });
  } finally {
    globalThis.fetch = originalFetch;
  }

  assert.match(calls[0].url, /\/holidays\/$/);
  assert.match(calls[1].url, /\/holidays\/admin\/$/);
  assert.equal(calls[2].options.method, "POST");
  assert.equal(JSON.parse(calls[2].options.body).name, "Republic Day");
  assert.equal(calls[3].options.method, "PATCH");
  assert.equal(JSON.parse(calls[3].options.body).is_active, false);
});

test("holiday API failures reject instead of silently returning an empty holiday list", async () => {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: "Unavailable" }), { status: 503 });
  try {
    await assert.rejects(fetchActiveHolidays(), /Unavailable/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
