import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { test, expect } from "vitest";
import { AdminAttendancePage } from "../src/components/admin/AdminAttendancePage.jsx";
import { FeedbackProvider } from "../src/feedback/FeedbackProvider.jsx";
import { API_BASE_URL } from "../src/lib/api.js";
import { server } from "./mocks/server.js";

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <FeedbackProvider>
        <AdminAttendancePage />
      </FeedbackProvider>
    </QueryClientProvider>,
  );
}

function attendanceFor(request) {
  const date = new URL(request.url).searchParams.get("date");
  return [
    {
      employee: "alice@example.test",
      employee_name: "Alice Employee",
      section: "People",
      subsection: "Recruiting",
      date,
      status: "INCOMPLETE",
      check_in: "2026-10-14T09:00:00Z",
      check_out: null,
      working_duration: "04:00:00",
    },
    {
      employee: "bob@example.test",
      employee_name: "Bob Employee",
      section: "Engineering",
      subsection: "Platform",
      date,
      status: "PRESENT",
      check_in: "2026-10-14T09:00:00Z",
      check_out: "2026-10-14T17:00:00Z",
      working_duration: "08:00:00",
    },
  ];
}

test("filters visible attendance rows as the administrator searches", async () => {
  server.use(
    http.get(`${API_BASE_URL}/admin/attendance/`, ({ request }) =>
      HttpResponse.json(attendanceFor(request)),
    ),
  );
  const user = userEvent.setup();
  renderPage();

  expect(await screen.findByText("Alice Employee")).toBeInTheDocument();
  expect(screen.getByText("Bob Employee")).toBeInTheDocument();
  await user.type(screen.getByPlaceholderText("Search employees..."), "alice@example.test");

  expect(screen.getByText("Alice Employee")).toBeInTheDocument();
  expect(screen.queryByText("Bob Employee")).not.toBeInTheDocument();
  await user.clear(screen.getByPlaceholderText("Search employees..."));
  await user.type(screen.getByPlaceholderText("Search employees..."), "nobody");
  expect(screen.getByText("No records match your filters.")).toBeInTheDocument();
});

test("sends a checkout request for the selected employee and reports success", async () => {
  let checkoutPayload;
  let requestedDate;
  server.use(
    http.get(`${API_BASE_URL}/admin/attendance/`, ({ request }) => {
      requestedDate = new URL(request.url).searchParams.get("date");
      return HttpResponse.json(attendanceFor(request));
    }),
    http.post(`${API_BASE_URL}/admin/force-checkout/`, async ({ request }) => {
      checkoutPayload = await request.json();
      return HttpResponse.json({ ok: true });
    }),
  );
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("Alice Employee");

  const aliceRow = screen.getByText("Alice Employee").closest("tr");
  await user.click(within(aliceRow).getByRole("button", { name: "Checkout" }));

  await waitFor(() =>
    expect(checkoutPayload).toEqual({
      employee: "alice@example.test",
      date: requestedDate,
    }),
  );
  expect(await screen.findByText("Checked out successfully.")).toBeInTheDocument();
});

test("shows a recovery action when attendance fails to load", async () => {
  let attempts = 0;
  server.use(
    http.get(`${API_BASE_URL}/admin/attendance/`, ({ request }) => {
      attempts += 1;
      if (attempts === 1) return HttpResponse.json({ detail: "Unavailable" }, { status: 503 });
      return HttpResponse.json(attendanceFor(request));
    }),
  );
  const user = userEvent.setup();
  renderPage();

  expect(await screen.findByText("Could not load attendance.")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByText("Alice Employee")).toBeInTheDocument();
  expect(attempts).toBe(2);
});
