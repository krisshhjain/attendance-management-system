import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { test, expect, vi } from "vitest";
import { AdminAttendancePage } from "../src/components/admin/AdminAttendancePage.jsx";
import { FeedbackProvider } from "../src/feedback/FeedbackProvider.jsx";
import { API_BASE_URL } from "../src/lib/api.js";
import { server } from "./mocks/server.js";

const spreadsheet = vi.hoisted(() => ({
  aoaToSheet: vi.fn((rows) => ({ rows })),
  bookNew: vi.fn(() => ({ sheets: [] })),
  appendSheet: vi.fn((workbook, sheet, name) => workbook.sheets.push({ sheet, name })),
  writeFile: vi.fn(),
}));
vi.mock("xlsx", () => ({
  utils: {
    aoa_to_sheet: (...args) => spreadsheet.aoaToSheet(...args),
    book_new: (...args) => spreadsheet.bookNew(...args),
    book_append_sheet: (...args) => spreadsheet.appendSheet(...args),
  },
  writeFile: (...args) => spreadsheet.writeFile(...args),
}));

function renderPage(props) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <FeedbackProvider>
        <AdminAttendancePage {...props} />
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
}, 15_000);

test("exports the currently filtered attendance rows to a dated workbook", async () => {
  server.use(
    http.get(`${API_BASE_URL}/admin/attendance/`, ({ request }) =>
      HttpResponse.json({ results: attendanceFor(request) }),
    ),
  );
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("Alice Employee");
  await user.type(screen.getByPlaceholderText("Search employees..."), "Alice");
  await user.click(screen.getByRole("button", { name: "Download Excel" }));

  await waitFor(() => expect(spreadsheet.writeFile).toHaveBeenCalledOnce());
  const [workbook, filename] = spreadsheet.writeFile.mock.calls[0];
  expect(filename).toMatch(/^attendance_\d{4}-\d{2}-\d{2}\.xlsx$/);
  expect(workbook.sheets[0].name).toBe("Attendance");
  expect(spreadsheet.aoaToSheet.mock.calls[0][0]).toEqual([
    [
      "Employee",
      "Email",
      "Section",
      "Subsection",
      "Date",
      "Status",
      "Check In",
      "Check Out",
      "Working Hours",
    ],
    [
      "Alice Employee",
      "alice@example.test",
      "People",
      "Recruiting",
      expect.any(String),
      "INCOMPLETE",
      expect.any(String),
      "",
      expect.any(String),
    ],
  ]);
});

test("filters attendance by status when the API returns a paginated result envelope", async () => {
  server.use(
    http.get(`${API_BASE_URL}/admin/attendance/`, ({ request }) =>
      HttpResponse.json({ results: attendanceFor(request) }),
    ),
  );
  const user = userEvent.setup();
  renderPage();
  expect(await screen.findByText("Alice Employee")).toBeInTheDocument();
  await user.click(screen.getByRole("combobox"));
  await user.click(screen.getByRole("option", { name: "Present" }));
  expect(screen.getByText("Bob Employee")).toBeInTheDocument();
  expect(screen.queryByText("Alice Employee")).not.toBeInTheDocument();
  await user.click(screen.getByRole("combobox"));
  await user.click(screen.getByRole("option", { name: "Absent" }));
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

test("checks out every incomplete employee in the selected date", async () => {
  let payload;
  server.use(
    http.get(`${API_BASE_URL}/admin/attendance/`, ({ request }) =>
      HttpResponse.json(attendanceFor(request)),
    ),
    http.post(`${API_BASE_URL}/admin/force-checkout/`, async ({ request }) => {
      payload = await request.json();
      return HttpResponse.json({ ok: true });
    }),
  );
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("Alice Employee");
  await user.click(screen.getByRole("button", { name: "Checkout All" }));
  await waitFor(() => expect(payload).toEqual({ all: true, date: expect.any(String) }));
  expect(await screen.findByText("Employees checked out successfully.")).toBeInTheDocument();
}, 15_000);

test("requires an edit reason and saves attendance corrections", async () => {
  let payload;
  server.use(
    http.get(`${API_BASE_URL}/admin/attendance/`, ({ request }) =>
      HttpResponse.json(attendanceFor(request)),
    ),
    http.post(`${API_BASE_URL}/admin/attendance/edit/`, async ({ request }) => {
      payload = await request.json();
      return HttpResponse.json({ ok: true });
    }),
  );
  const user = userEvent.setup();
  renderPage({ allowEdit: true });
  await screen.findByText("Alice Employee");
  const aliceRow = screen.getByText("Alice Employee").closest("tr");
  await user.click(within(aliceRow).getByRole("button", { name: "Edit" }));
  const save = screen.getByRole("button", { name: "Save Changes" });
  expect(save).toBeDisabled();
  await user.type(screen.getByLabelText("Reason for correction"), "Manager verified the times");
  await user.click(save);
  await waitFor(() =>
    expect(payload).toEqual(
      expect.objectContaining({
        employee: "alice@example.test",
        reason: "Manager verified the times",
        status: "INCOMPLETE",
      }),
    ),
  );
  expect(await screen.findByText("Attendance updated successfully.")).toBeInTheDocument();
}, 15_000);

test("requires a reset reason before clearing today's attendance", async () => {
  let payload;
  server.use(
    http.get(`${API_BASE_URL}/admin/attendance/`, ({ request }) =>
      HttpResponse.json(attendanceFor(request)),
    ),
    http.post(`${API_BASE_URL}/admin/attendance/reset/`, async ({ request }) => {
      payload = await request.json();
      return HttpResponse.json({ ok: true });
    }),
  );
  const user = userEvent.setup();
  renderPage({ allowReset: true });
  await screen.findByText("Alice Employee");
  const aliceRow = screen.getByText("Alice Employee").closest("tr");
  await user.click(within(aliceRow).getByRole("button", { name: "Reset" }));
  const reset = screen.getByRole("button", { name: "Reset Attendance" });
  expect(reset).toBeDisabled();
  await user.type(screen.getByLabelText("Reason for reset"), "Duplicate punch");
  await user.click(reset);
  await waitFor(() =>
    expect(payload).toEqual({
      employee: "alice@example.test",
      reason: "Duplicate punch",
      reset_type: "both",
    }),
  );
  expect(await screen.findByText("Attendance reset successfully.")).toBeInTheDocument();
}, 15_000);

test("reports checkout failures without removing attendance records", async () => {
  server.use(
    http.get(`${API_BASE_URL}/admin/attendance/`, ({ request }) =>
      HttpResponse.json(attendanceFor(request)),
    ),
    http.post(`${API_BASE_URL}/admin/force-checkout/`, () =>
      HttpResponse.json(
        { detail: "Checkout is blocked by the attendance policy." },
        { status: 409 },
      ),
    ),
  );
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("Alice Employee");
  const aliceRow = screen.getByText("Alice Employee").closest("tr");
  await user.click(within(aliceRow).getByRole("button", { name: "Checkout" }));

  expect(
    await screen.findByText("Checkout is blocked by the attendance policy."),
  ).toBeInTheDocument();
  expect(screen.getByText("Alice Employee")).toBeInTheDocument();
  expect(screen.queryByText("Checked out successfully.")).not.toBeInTheDocument();
});
