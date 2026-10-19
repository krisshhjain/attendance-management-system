import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { ManagerManagement } from "../src/components/ManagerManagement.jsx";
import { API_BASE_URL } from "../src/lib/api.js";
import { server } from "./mocks/server.js";

const state = vi.hoisted(() => ({ success: vi.fn(), notifyError: vi.fn() }));
vi.mock("../src/feedback/useFeedback.js", () => ({
  useFeedback: () => ({ success: state.success, notifyError: state.notifyError }),
}));

const manager = {
  id: 12,
  first_name: "Avery",
  last_name: "Lee",
  email: "avery@example.test",
  is_active: true,
  scopes: [
    { scope_type: "SECTION", value: "A" },
    { scope_type: "DEPARTMENT", value: "People" },
  ],
  hr_copilot_subsections: ["A1"],
};

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ManagerManagement />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  server.use(
    http.get(`${API_BASE_URL}/admin/employees/managers/list/`, () => HttpResponse.json([manager])),
  );
});

test("creates a manager from the account form and refreshes the manager list", async () => {
  const user = userEvent.setup();
  let created;
  server.use(
    http.post(`${API_BASE_URL}/admin/employees/managers/`, async ({ request }) => {
      created = await request.json();
      return HttpResponse.json({ id: 13, ...created }, { status: 201 });
    }),
  );
  renderPage();
  await screen.findByText("Avery Lee");
  await user.click(screen.getByRole("button", { name: "Create Manager" }));
  const dialog = screen.getByRole("dialog");
  await user.type(within(dialog).getByRole("textbox", { name: "First Name" }), "Morgan");
  await user.type(within(dialog).getByRole("textbox", { name: "Last Name" }), "Chen");
  await user.type(within(dialog).getByRole("textbox", { name: "Email" }), "morgan@example.test");
  await user.type(dialog.querySelector('input[type="password"]'), "strong-pass-1");
  await user.click(within(dialog).getByRole("button", { name: "Create Manager" }));

  await waitFor(() => expect(state.success).toHaveBeenCalledWith("Manager created successfully."));
  expect(created).toMatchObject({
    email: "morgan@example.test",
    first_name: "Morgan",
    last_name: "Chen",
    password: "strong-pass-1",
    scopes: [],
  });
}, 15_000);

test("updates the selected manager details while retaining assigned scopes", async () => {
  const user = userEvent.setup();
  let update;
  server.use(
    http.patch(`${API_BASE_URL}/admin/employees/managers/12/`, async ({ request }) => {
      update = await request.json();
      return HttpResponse.json({ ...manager, ...update });
    }),
  );
  renderPage();
  const row = await screen.findByRole("row", { name: /Avery Lee/ });
  await user.click(within(row).getByTestId("EditIcon"));
  const dialog = screen.getByRole("dialog");
  const firstName = within(dialog).getByRole("textbox", { name: "First Name" });
  await user.clear(firstName);
  await waitFor(() => expect(firstName).toHaveValue(""));
  await user.type(firstName, "Avery-Jane");
  await user.click(within(dialog).getByRole("button", { name: "Update Manager" }));

  await waitFor(() => expect(state.success).toHaveBeenCalledWith("Manager updated successfully."));
  expect(update).toMatchObject({
    first_name: "Avery-Jane",
    scopes: [
      { scope_type: "SECTION", value: "A" },
      { scope_type: "DEPARTMENT", value: "People" },
    ],
  });
}, 15_000);

test("validates a replacement password and submits the matching value", async () => {
  const user = userEvent.setup();
  let passwordBody;
  server.use(
    http.post(
      `${API_BASE_URL}/admin/employees/managers/12/change-password/`,
      async ({ request }) => {
        passwordBody = await request.json();
        return HttpResponse.json({ ok: true });
      },
    ),
  );
  renderPage();
  const row = await screen.findByRole("row", { name: /Avery Lee/ });
  await user.click(within(row).getByTestId("KeyIcon"));
  const dialog = screen.getByRole("dialog");
  const [newPassword, confirmPassword] = dialog.querySelectorAll('input[type="password"]');
  await user.type(newPassword, "different-1");
  await user.type(confirmPassword, "different-2");
  await user.click(within(dialog).getByRole("button", { name: "Change Password" }));
  expect(await within(dialog).findByText("Passwords do not match")).toBeInTheDocument();

  await user.clear(confirmPassword);
  await user.type(confirmPassword, "different-1");
  await user.click(within(dialog).getByRole("button", { name: "Change Password" }));
  await waitFor(() =>
    expect(state.success).toHaveBeenCalledWith("Manager password changed successfully."),
  );
  expect(passwordBody).toEqual({ new_password: "different-1" });
});

test("requires explicit confirmation before removing a manager", async () => {
  const user = userEvent.setup();
  let deleted = false;
  server.use(
    http.delete(`${API_BASE_URL}/admin/employees/managers/12/`, () => {
      deleted = true;
      return new HttpResponse(null, { status: 204 });
    }),
  );
  renderPage();
  const row = await screen.findByRole("row", { name: /Avery Lee/ });
  await user.click(within(row).getByTestId("DeleteIcon"));
  const dialog = screen.getByRole("dialog");
  expect(dialog).toHaveTextContent(/Avery Lee/);
  expect(deleted).toBe(false);
  await user.click(within(dialog).getByRole("button", { name: "Delete Manager" }));

  await waitFor(() => expect(state.success).toHaveBeenCalledWith("Manager deleted successfully."));
  expect(deleted).toBe(true);
});
