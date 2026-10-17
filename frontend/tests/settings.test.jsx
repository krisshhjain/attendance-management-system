import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { Route } from "../src/routes/settings.jsx";
import { API_BASE_URL } from "../src/lib/api.js";
import { server } from "./mocks/server.js";

const state = vi.hoisted(() => ({ success: vi.fn(), notifyError: vi.fn() }));
vi.mock("@tanstack/react-router", () => ({ createFileRoute: () => (options) => options }));
vi.mock("../src/components/RequireAuth.jsx", () => ({ RequireAuth: ({ children }) => children }));
vi.mock("../src/feedback/useFeedback.js", () => ({
  useFeedback: () => ({ success: state.success, notifyError: state.notifyError }),
}));

function renderPage() {
  const Component = Route.component;
  return render(<Component />);
}

async function openPasswordDialog(user) {
  await user.click(screen.getByRole("button", { name: "Change" }));
  return screen.getByRole("dialog");
}

beforeEach(() => vi.clearAllMocks());

test("enforces matching passwords and each password complexity requirement before saving", async () => {
  let submitted = false;
  server.use(
    http.post(`${API_BASE_URL}/auth/change-password/`, () => {
      submitted = true;
      return HttpResponse.json({ ok: true });
    }),
  );
  const user = userEvent.setup();
  renderPage();
  const dialog = await openPasswordDialog(user);
  const current = within(dialog).getByLabelText(/Current Password/);
  const password = within(dialog).getByLabelText(/^New Password/);
  const confirm = within(dialog).getByLabelText(/Confirm New Password/);
  await user.type(current, "old-password");

  await user.type(password, "Mismatch1!");
  await user.type(confirm, "Mismatch2!");
  await user.click(within(dialog).getByRole("button", { name: "Update" }));
  expect(await within(dialog).findByText("New passwords do not match.")).toBeInTheDocument();

  const invalidPasswords = [
    ["short", "Password must be at least 8 characters long."],
    ["longpassword1!", "Password must contain at least 1 capital letter."],
    ["UPPERCASE1!", "Password must contain at least 1 lowercase letter."],
    ["Password1", "Password must contain at least 1 symbol."],
  ];
  for (const [value, message] of invalidPasswords) {
    await user.clear(password);
    await user.clear(confirm);
    await user.type(password, value);
    await user.type(confirm, value);
    await user.click(within(dialog).getByRole("button", { name: "Update" }));
    expect(await within(dialog).findByText(message)).toBeInTheDocument();
  }

  await user.clear(password);
  await user.clear(confirm);
  await user.type(password, "Password1!");
  await user.type(confirm, "Password1!");
  await user.click(within(dialog).getByRole("button", { name: "Update" }));

  await waitFor(() => expect(state.success).toHaveBeenCalledWith("Password changed successfully."));
  expect(submitted).toBe(true);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
}, 30_000);

test("keeps the dialog open and reports a rejected current password", async () => {
  let body;
  server.use(
    http.post(`${API_BASE_URL}/auth/change-password/`, async ({ request }) => {
      body = await request.json();
      return HttpResponse.json({ detail: "Current password is incorrect." }, { status: 400 });
    }),
  );
  const user = userEvent.setup();
  renderPage();
  const dialog = await openPasswordDialog(user);
  const current = within(dialog).getByLabelText(/Current Password/);
  await user.clear(current);
  await user.type(current, "wrong-current");
  await user.type(within(dialog).getByLabelText(/^New Password/), "SecurePass1!");
  await user.type(within(dialog).getByLabelText(/Confirm New Password/), "SecurePass1!");
  await user.click(within(dialog).getByRole("button", { name: "Update" }));

  await waitFor(() =>
    expect(state.notifyError).toHaveBeenCalledWith(
      expect.objectContaining({ message: "Current password is incorrect." }),
      expect.objectContaining({ title: "Password change failed" }),
    ),
  );
  expect(body).toEqual({ current_password: "wrong-current", new_password: "SecurePass1!" });
  expect(screen.getByRole("dialog")).toBeInTheDocument();
}, 15_000);
