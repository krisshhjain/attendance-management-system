import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, expect, test, vi } from "vitest";
import { ShiftAssignmentDialog } from "../src/components/dashboard/ShiftAssignmentDialog.jsx";
import { API_BASE_URL } from "../src/lib/api.js";
import { server } from "./mocks/server.js";

const feedback = vi.hoisted(() => ({ success: vi.fn() }));
vi.mock("../src/feedback/useFeedback.js", () => ({ useFeedback: () => feedback }));

const employee = {
  id: 15,
  email: "avery@example.test",
  first_name: "Avery",
  last_name: "Lee",
  employment_type: "PERMANENT",
  shift: { id: 4, code: "OLD", name: "Old Shift", start_time: "08:00", end_time: "16:00" },
};
const shifts = [
  {
    id: 4,
    code: "OLD",
    name: "Old Shift",
    employment_type: "PERMANENT",
    start_time: "08:00",
    end_time: "16:00",
  },
  {
    id: 7,
    code: "DAY",
    name: "Day Shift",
    employment_type: "PERMANENT",
    start_time: "09:00",
    end_time: "17:00",
  },
  {
    id: 8,
    code: "TEMP",
    name: "Temporary Shift",
    employment_type: "CONTRACT",
    start_time: "10:00",
    end_time: "18:00",
  },
];

function renderDialog(props = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ShiftAssignmentDialog
        open
        employee={employee}
        onClose={vi.fn()}
        onSuccess={vi.fn()}
        {...props}
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  server.use(
    http.get(`${API_BASE_URL}/attendance/admin/shift/all/`, () => HttpResponse.json({ shifts })),
  );
});

test("assigns a shift matching the employee's type and refreshes the employee list", async () => {
  let payload;
  const onSuccess = vi.fn();
  server.use(
    http.post(`${API_BASE_URL}/attendance/admin/shift/assign/`, async ({ request }) => {
      payload = await request.json();
      return HttpResponse.json({ ok: true });
    }),
  );
  const user = userEvent.setup();
  renderDialog({ onSuccess });

  expect(await screen.findByText("OLD - Old Shift")).toBeInTheDocument();
  await waitFor(() => expect(screen.getByRole("combobox", { name: "New Shift" })).toBeEnabled());
  await user.click(screen.getByRole("combobox", { name: "New Shift" }));
  expect(screen.getByRole("option", { name: /DAY - Day Shift/ })).toBeInTheDocument();
  expect(screen.queryByRole("option", { name: /Temporary Shift/ })).not.toBeInTheDocument();
  await user.click(screen.getByRole("option", { name: /DAY - Day Shift/ }));
  await user.click(screen.getByRole("button", { name: "Assign Shift" }));

  await waitFor(() =>
    expect(payload).toEqual({ employee_email: "avery@example.test", shift_id: 7 }),
  );
  expect(onSuccess).toHaveBeenCalledOnce();
  expect(feedback.success).toHaveBeenCalledWith("Employee shift assigned successfully.");
});

test("allows removing the current assignment and displays an API error", async () => {
  server.use(
    http.post(`${API_BASE_URL}/attendance/admin/shift/assign/`, () =>
      HttpResponse.json({ detail: "Shift is locked by payroll." }, { status: 409 }),
    ),
  );
  const user = userEvent.setup();
  renderDialog();

  await screen.findByText("OLD - Old Shift");
  await waitFor(() => expect(screen.getByRole("combobox", { name: "New Shift" })).toBeEnabled());
  await user.click(screen.getByRole("combobox", { name: "New Shift" }));
  await user.click(screen.getByRole("option", { name: "No Shift (Remove Assignment)" }));
  await user.click(screen.getByRole("button", { name: "Assign Shift" }));
  expect(await screen.findByText("Shift is locked by payroll.")).toBeInTheDocument();
});
