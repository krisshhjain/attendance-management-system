import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test, vi } from "vitest";
import { EmployeeTable } from "../src/components/dashboard/EmployeeTable.jsx";
import { OrganizationScopeProvider } from "../src/lib/organizationScope.jsx";
import { FeedbackProvider } from "../src/feedback/FeedbackProvider.jsx";
import { API_BASE_URL } from "../src/lib/api.js";
import { server } from "./mocks/server.js";

vi.mock("../src/components/dashboard/AddEmployeeDialog.jsx", () => ({
  AddEmployeeDialog: ({ open, onClose, onSuccess }) =>
    open ? (
      <div role="dialog" aria-label="Add employee dialog">
        <button onClick={onSuccess}>Complete add</button>
        <button onClick={onClose}>Close add</button>
      </div>
    ) : null,
}));
vi.mock("../src/components/dashboard/EditEmployeeDialog.jsx", () => ({
  EditEmployeeDialog: ({ open, employee, onClose, onSuccess }) =>
    open ? (
      <div role="dialog" aria-label="Edit employee dialog">
        <span>{employee.email}</span>
        <button onClick={onSuccess}>Complete edit</button>
        <button onClick={onClose}>Close edit</button>
      </div>
    ) : null,
}));
vi.mock("../src/components/dashboard/ChangePasswordDialog.jsx", () => ({
  ChangePasswordDialog: ({ open, employee, onClose }) =>
    open ? (
      <div role="dialog" aria-label="Change password dialog">
        <span>{employee.email}</span>
        <button onClick={onClose}>Close password</button>
      </div>
    ) : null,
}));
vi.mock("../src/components/dashboard/ShiftAssignmentDialog.jsx", () => ({
  ShiftAssignmentDialog: ({ open, employee, onClose, onSuccess }) =>
    open ? (
      <div role="dialog" aria-label="Assign shift dialog">
        <span>{employee.email}</span>
        <button onClick={onSuccess}>Complete shift</button>
        <button onClick={onClose}>Close shift</button>
      </div>
    ) : null,
}));
vi.mock("../src/components/WebcamCapture.jsx", () => ({ default: () => null }));

function renderTable() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <OrganizationScopeProvider>
        <FeedbackProvider>
          <EmployeeTable />
        </FeedbackProvider>
      </OrganizationScopeProvider>
    </QueryClientProvider>,
  );
}

const employees = [
  {
    id: 4,
    first_name: "Avery",
    last_name: "Lee",
    email: "avery@example.test",
    department: "People",
    section: "Recruiting",
    subsection: "Hiring",
    employment_type: "PERMANENT",
    is_active: true,
    has_face_enrolled: true,
    shift: { code: "DAY", start_time: "09:00", end_time: "17:00" },
  },
  {
    id: 5,
    first_name: "Jordan",
    last_name: "Park",
    email: "jordan@example.test",
    department: "Operations",
    employment_type: "CONTRACT",
    is_active: false,
    has_face_enrolled: false,
    shift: null,
  },
  {
    id: 6,
    email: "taylor@example.test",
    department: "Support",
    is_active: true,
    has_face_enrolled: false,
    shift: null,
  },
];

test("searches employees by name or email and applies employment/status filters", async () => {
  server.use(http.get(`${API_BASE_URL}/admin/employees/list/`, () => HttpResponse.json(employees)));
  const user = userEvent.setup();
  renderTable();

  expect(await screen.findByText("Avery Lee")).toBeInTheDocument();
  expect(screen.getByText("Jordan Park")).toBeInTheDocument();
  await user.type(screen.getByPlaceholderText("Search employees..."), "jordan@");
  expect(screen.getByText("Jordan Park")).toBeInTheDocument();
  expect(screen.queryByText("Avery Lee")).not.toBeInTheDocument();
  await user.clear(screen.getByPlaceholderText("Search employees..."));

  const selects = screen.getAllByRole("combobox");
  await user.click(selects[0]);
  await user.click(screen.getByRole("option", { name: "Permanent" }));
  expect(screen.getAllByText("Avery Lee").length).toBeGreaterThan(0);
  expect(screen.queryByText("Jordan Park")).not.toBeInTheDocument();
  expect(screen.getByText("DAY")).toBeInTheDocument();
});

test("filters inactive and active employees independently and supports fallback names", async () => {
  server.use(http.get(`${API_BASE_URL}/admin/employees/list/`, () => HttpResponse.json(employees)));
  const user = userEvent.setup();
  renderTable();

  expect(await screen.findByText("taylor")).toBeInTheDocument();
  const statusFilter = screen.getAllByRole("combobox")[1];
  await user.click(statusFilter);
  await user.click(screen.getByRole("option", { name: "Inactive" }));
  expect(screen.getByText("Jordan Park")).toBeInTheDocument();
  expect(screen.queryByText("Avery Lee")).not.toBeInTheDocument();

  await user.click(screen.getAllByRole("combobox")[1]);
  await user.click(screen.getByRole("option", { name: "Active" }));
  expect(screen.getAllByText("Avery Lee").length).toBeGreaterThan(0);
  expect(screen.getByText("taylor")).toBeInTheDocument();
  expect(screen.queryByText("Jordan Park")).not.toBeInTheDocument();
});

test("opens employee actions with the selected record and refreshes after saved changes", async () => {
  let loads = 0;
  server.use(
    http.get(`${API_BASE_URL}/admin/employees/list/`, () => {
      loads += 1;
      return HttpResponse.json(employees);
    }),
  );
  const user = userEvent.setup();
  renderTable();
  const row = (await screen.findByText("Avery Lee")).closest("tr");
  const actions = within(row).getAllByRole("button");

  await user.click(screen.getByRole("button", { name: "Add Employee" }));
  expect(screen.getByRole("dialog", { name: "Add employee dialog" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Complete add" }));
  await waitFor(() => expect(loads).toBe(2));

  await user.click(actions[3]);
  expect(screen.getByRole("dialog", { name: "Edit employee dialog" })).toHaveTextContent(
    "avery@example.test",
  );
  await user.click(screen.getByRole("button", { name: "Complete edit" }));
  await waitFor(() => expect(loads).toBe(3));

  await user.click(actions[2]);
  expect(screen.getByRole("dialog", { name: "Change password dialog" })).toHaveTextContent(
    "avery@example.test",
  );
  await user.click(screen.getByRole("button", { name: "Close password" }));

  await user.click(actions[0]);
  expect(screen.getByRole("dialog", { name: "Assign shift dialog" })).toHaveTextContent(
    "avery@example.test",
  );
  await user.click(screen.getByRole("button", { name: "Complete shift" }));
  await waitFor(() => expect(loads).toBe(4));
});

test("confirms employee deletion, reports success, and refreshes the list", async () => {
  let deleted = false;
  server.use(
    http.get(`${API_BASE_URL}/admin/employees/list/`, () =>
      HttpResponse.json(deleted ? [employees[1]] : employees),
    ),
    http.delete(`${API_BASE_URL}/admin/employees/4/`, () => {
      deleted = true;
      return HttpResponse.json({ ok: true });
    }),
  );
  const user = userEvent.setup();
  renderTable();
  const name = await screen.findByText("Avery Lee");
  const row = name.closest("tr");
  const actions = within(row).getAllByRole("button");
  await user.click(actions.at(-1));
  expect(screen.getByText("Delete Employee?")).toBeInTheDocument();
  expect(screen.getByRole("dialog")).toHaveTextContent("This will permanently delete Avery Lee");
  await user.click(screen.getByRole("button", { name: "Delete", exact: true }));

  await waitFor(() => expect(screen.queryByText("Avery Lee")).not.toBeInTheDocument());
  expect(await screen.findByText("Employee deleted successfully.")).toBeInTheDocument();
});

test("keeps the selected employee when deletion is rejected", async () => {
  server.use(
    http.get(`${API_BASE_URL}/admin/employees/list/`, () => HttpResponse.json(employees)),
    http.delete(`${API_BASE_URL}/admin/employees/4/`, () =>
      HttpResponse.json({ detail: "Employee has active payroll records." }, { status: 409 }),
    ),
  );
  const user = userEvent.setup();
  renderTable();
  const row = (await screen.findByText("Avery Lee")).closest("tr");
  await user.click(within(row).getAllByRole("button").at(-1));
  await user.click(screen.getByRole("button", { name: "Delete", exact: true }));

  expect(await screen.findByText("Employee has active payroll records.")).toBeInTheDocument();
  expect(screen.getByText("Delete Employee?")).toBeInTheDocument();
  expect(screen.getAllByText("Avery Lee").length).toBeGreaterThan(0);
});
test("shows a retry action when the employee endpoint is unavailable", async () => {
  let attempts = 0;
  server.use(
    http.get(`${API_BASE_URL}/admin/employees/list/`, () => {
      attempts += 1;
      if (attempts === 1) return HttpResponse.json({ detail: "Unavailable" }, { status: 503 });
      return HttpResponse.json(employees);
    }),
  );
  const user = userEvent.setup();
  renderTable();

  expect(await screen.findByText("Unable to load employees. Try again.")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByText("Avery Lee")).toBeInTheDocument();
  expect(attempts).toBe(2);
});
