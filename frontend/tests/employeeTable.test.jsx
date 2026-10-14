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
  AddEmployeeDialog: () => null,
}));
vi.mock("../src/components/dashboard/EditEmployeeDialog.jsx", () => ({
  EditEmployeeDialog: () => null,
}));
vi.mock("../src/components/dashboard/ChangePasswordDialog.jsx", () => ({
  ChangePasswordDialog: () => null,
}));
vi.mock("../src/components/dashboard/ShiftAssignmentDialog.jsx", () => ({
  ShiftAssignmentDialog: () => null,
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
  expect(screen.getByText("Avery Lee")).toBeInTheDocument();
  expect(screen.queryByText("Jordan Park")).not.toBeInTheDocument();
  expect(screen.getByText("DAY")).toBeInTheDocument();
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
