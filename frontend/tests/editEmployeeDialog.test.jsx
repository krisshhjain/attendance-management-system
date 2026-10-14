import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { API_BASE_URL } from "../src/lib/api.js";
import { EditEmployeeDialog } from "../src/components/dashboard/EditEmployeeDialog.jsx";
import { server } from "./mocks/server.js";

const feedback = vi.hoisted(() => ({ success: vi.fn() }));
vi.mock("../src/feedback/FeedbackProvider.jsx", () => ({ useFeedback: () => feedback }));

const employee = {
  id: 17,
  first_name: "Riya",
  last_name: "Shah",
  email: "riya@example.test",
  department: "Engineering",
  employment_type: "PERMANENT",
  date_joined: "2024-04-15",
  is_active: true,
  app_access: { dashboard: true, attendance: true, leave: false },
};

beforeEach(() => vi.clearAllMocks());

test("updates organization details, employment status, and area access", async () => {
  let requestBody;
  const onClose = vi.fn();
  const onSuccess = vi.fn();
  server.use(
    http.patch(`${API_BASE_URL}/admin/employees/17/`, async ({ request }) => {
      requestBody = await request.json();
      return HttpResponse.json({ ...employee, ...requestBody });
    }),
  );
  const user = userEvent.setup();
  render(<EditEmployeeDialog open employee={employee} onClose={onClose} onSuccess={onSuccess} />);
  const dialog = screen.getByRole("dialog");

  expect(within(dialog).getByLabelText(/First Name/)).toHaveValue("Riya");
  await user.clear(within(dialog).getByLabelText(/Department/));
  await user.type(within(dialog).getByLabelText(/Department/), "People");
  await user.click(within(dialog).getByRole("combobox", { name: "Employment Type" }));
  await user.click(screen.getByRole("option", { name: "INTERN" }));
  await user.type(within(dialog).getByLabelText(/Section/), "B");
  await user.type(within(dialog).getByLabelText(/Subsection/), "B3");
  fireEvent.change(within(dialog).getByLabelText(/Date Joined/), {
    target: { value: "2025-01-06" },
  });
  await user.click(within(dialog).getByLabelText("Active"));
  await user.click(within(dialog).getByRole("checkbox", { name: "Attendance" }));
  await user.click(within(dialog).getByRole("button", { name: "Save Changes" }));

  await waitFor(() => expect(onSuccess).toHaveBeenCalledOnce());
  expect(requestBody).toEqual({
    first_name: "Riya",
    last_name: "Shah",
    department: "People",
    section: "B",
    subsection: "B3",
    employment_type: "INTERN",
    date_joined: "2025-01-06",
    is_active: false,
    app_access: { dashboard: true, attendance: false, leave: false },
  });
  expect(feedback.success).toHaveBeenCalledWith("Employee updated successfully.");
  expect(onClose).not.toHaveBeenCalled();
});

test("reports a rejected update and retains the edited values", async () => {
  server.use(
    http.patch(`${API_BASE_URL}/admin/employees/17/`, () =>
      HttpResponse.json({ detail: "The department is not available." }, { status: 400 }),
    ),
  );
  const user = userEvent.setup();
  render(<EditEmployeeDialog open employee={employee} onClose={vi.fn()} onSuccess={vi.fn()} />);
  const dialog = screen.getByRole("dialog");
  const name = within(dialog).getByLabelText(/First Name/);
  await user.clear(name);
  await user.type(name, "Ria");
  await user.click(within(dialog).getByRole("button", { name: "Save Changes" }));

  expect(await within(dialog).findByText("The department is not available.")).toBeInTheDocument();
  expect(name).toHaveValue("Ria");
});

test("renders nothing without an employee and closes when cancelled", async () => {
  const onClose = vi.fn();
  const { rerender } = render(
    <EditEmployeeDialog open employee={null} onClose={onClose} onSuccess={vi.fn()} />,
  );
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

  rerender(<EditEmployeeDialog open employee={employee} onClose={onClose} onSuccess={vi.fn()} />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Cancel" }));
  expect(onClose).toHaveBeenCalledOnce();
});
