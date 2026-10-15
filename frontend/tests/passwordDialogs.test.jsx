import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, expect, test, vi } from "vitest";
import { ForcePasswordChangeModal } from "../src/components/ForcePasswordChangeModal.jsx";
import { ChangePasswordDialog } from "../src/components/dashboard/ChangePasswordDialog.jsx";
import { API_BASE_URL } from "../src/lib/api.js";
import { server } from "./mocks/server.js";

const state = vi.hoisted(() => ({
  logout: vi.fn(),
  refreshUser: vi.fn(),
  success: vi.fn(),
  notifyError: vi.fn(),
}));
vi.mock("../src/lib/auth.jsx", () => ({
  useAuth: () => ({ logout: state.logout, refreshUser: state.refreshUser }),
}));
vi.mock("../src/feedback/FeedbackProvider.jsx", () => ({
  useFeedback: () => ({ success: state.success, notifyError: state.notifyError }),
}));

beforeEach(() => {
  vi.clearAllMocks();
  server.use(
    http.post(`${API_BASE_URL}/auth/change-password/`, () => HttpResponse.json({ ok: true })),
    http.post(`${API_BASE_URL}/admin/employees/19/change-password/`, () =>
      HttpResponse.json({ ok: true }),
    ),
  );
});

test("requires a sufficiently long matching first-time password before saving", async () => {
  let payload;
  server.use(
    http.post(`${API_BASE_URL}/auth/change-password/`, async ({ request }) => {
      payload = await request.json();
      return HttpResponse.json({ ok: true });
    }),
  );
  const user = userEvent.setup();
  render(<ForcePasswordChangeModal open />);

  const [currentPassword, newPassword, confirmPassword] =
    document.querySelectorAll('input[type="password"]');
  await user.type(currentPassword, "temporary");
  await user.type(newPassword, "short");
  await user.type(confirmPassword, "short");
  await user.click(screen.getByRole("button", { name: "Set Password & Continue" }));
  expect(screen.getByText("New password must be at least 8 characters long.")).toBeInTheDocument();
  expect(payload).toBeUndefined();

  await user.clear(newPassword);
  await user.type(newPassword, "secure-pass-1");
  await user.clear(confirmPassword);
  await user.type(confirmPassword, "different-pass");
  await user.click(screen.getByRole("button", { name: "Set Password & Continue" }));
  expect(screen.getByText("New passwords do not match.")).toBeInTheDocument();
  expect(payload).toBeUndefined();

  await user.clear(confirmPassword);
  await user.type(confirmPassword, "secure-pass-1");
  await user.click(screen.getByRole("button", { name: "Set Password & Continue" }));
  await waitFor(() =>
    expect(payload).toEqual({ current_password: "temporary", new_password: "secure-pass-1" }),
  );
  expect(state.refreshUser).toHaveBeenCalledOnce();
  expect(state.success).toHaveBeenCalledWith("Password changed successfully.");
});

test("lets a user sign out instead of completing mandatory password setup", async () => {
  const user = userEvent.setup();
  render(<ForcePasswordChangeModal open />);
  await user.click(screen.getByRole("button", { name: "Sign Out" }));
  expect(state.logout).toHaveBeenCalledOnce();
});

test("validates and resets an employee password, then clears the form on cancel", async () => {
  let payload;
  server.use(
    http.post(`${API_BASE_URL}/admin/employees/19/change-password/`, async ({ request }) => {
      payload = await request.json();
      return HttpResponse.json({ ok: true });
    }),
  );
  const onClose = vi.fn();
  const onSuccess = vi.fn();
  const user = userEvent.setup();
  render(
    <ChangePasswordDialog
      open
      employee={{ id: 19, first_name: "Avery", last_name: "Lee", email: "avery@example.test" }}
      onClose={onClose}
      onSuccess={onSuccess}
    />,
  );

  expect(screen.getByText("Avery Lee")).toBeInTheDocument();
  const passwordInput = document.querySelector('input[type="password"]');
  await user.type(passwordInput, "short");
  await user.click(screen.getByRole("button", { name: "Reset Password" }));
  expect(screen.getByText("Password must be at least 8 characters long.")).toBeInTheDocument();
  expect(payload).toBeUndefined();

  await user.clear(passwordInput);
  await user.type(passwordInput, "ValidTest1!");
  await user.click(screen.getByRole("button", { name: "Reset Password" }));
  await waitFor(() => expect(payload).toEqual({ new_password: "ValidTest1!" }));
  expect(onSuccess).toHaveBeenCalledOnce();
  expect(state.success).toHaveBeenCalledWith("Employee password reset successfully.");

  await user.click(screen.getByRole("button", { name: "Cancel" }));
  expect(onClose).toHaveBeenCalledOnce();
});

test("shows the server reason when an employee password reset is rejected", async () => {
  server.use(
    http.post(`${API_BASE_URL}/admin/employees/19/change-password/`, () =>
      HttpResponse.json({ detail: "Password reset is not permitted." }, { status: 403 }),
    ),
  );
  const user = userEvent.setup();
  render(
    <ChangePasswordDialog
      open
      employee={{ id: 19, email: "avery@example.test" }}
      onClose={vi.fn()}
      onSuccess={vi.fn()}
    />,
  );
  await user.type(document.querySelector('input[type="password"]'), "temporary-2026");
  await user.click(screen.getByRole("button", { name: "Reset Password" }));
  expect(await screen.findByText("Password reset is not permitted.")).toBeInTheDocument();
});
