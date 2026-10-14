import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { test, expect } from "vitest";
import { API_BASE_URL } from "../src/lib/api.js";
import { server } from "./mocks/server.js";
import { useUpcomingHolidays } from "../src/data/holidayCalendar.js";

function createWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

test("loads, filters and orders active upcoming holidays", async () => {
  server.use(
    http.get(`${API_BASE_URL}/holidays/`, () =>
      HttpResponse.json([
        { date: "2999-12-25", name: "Year End", is_active: true },
        { date: "2000-01-01", name: "Past Holiday", is_active: true },
        { date: "2999-01-01", name: "Inactive Holiday", is_active: false },
        { date: "2999-01-02", name: "New Year", is_active: true },
      ]),
    ),
  );

  const { result } = renderHook(() => useUpcomingHolidays(), { wrapper: createWrapper() });

  await waitFor(() => expect(result.current.isSuccess).toBe(true));
  expect(result.current.holidays.map(({ name, color }) => ({ name, color }))).toEqual([
    { name: "New Year", color: "#6366f1" },
    { name: "Year End", color: "#6366f1" },
  ]);
});

test("exposes API failures to the holiday panel", async () => {
  server.use(
    http.get(`${API_BASE_URL}/holidays/`, () =>
      HttpResponse.json({ detail: "Unavailable" }, { status: 503 }),
    ),
  );
  const { result } = renderHook(() => useUpcomingHolidays(), { wrapper: createWrapper() });

  await waitFor(() => expect(result.current.isError).toBe(true));
  expect(result.current.holidays).toEqual([]);
});
