import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { Route } from "../src/routes/admin-regularization.jsx";

const state = vi.hoisted(() => ({
  user: { is_superuser: true },
  loginType: "admin",
  requests: vi.fn(),
  policy: vi.fn(),
  savePolicy: vi.fn(),
  feedback: { success: vi.fn(), notifyError: vi.fn() },
}));
vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (options) => options,
  Link: ({ children, ...props }) => <a {...props}>{children}</a>,
}));
vi.mock("../src/components/RequireAuth.jsx", () => ({
  RequireAuth: ({ children }) => children,
}));
vi.mock("../src/lib/useAuth.js", () => ({
  useAuth: () => ({ user: state.user, loginType: state.loginType }),
}));
vi.mock("../src/lib/api.js", () => ({
  fetchAdminRegularizationRequests: state.requests,
  fetchAdminRegularizationQuotaPolicy: state.policy,
  updateAdminRegularizationQuotaPolicy: state.savePolicy,
}));
vi.mock("../src/feedback/useFeedback.js", () => ({ useFeedback: () => state.feedback }));

function renderPage() {
  const Component = Route.component;
  return render(<Component />);
}

beforeEach(() => {
  vi.clearAllMocks();
  state.user = { is_superuser: true };
  state.loginType = "admin";
  state.requests.mockResolvedValue([
    {
      id: 24,
      employee_name: "Avery Lee",
      employee_email: "avery@example.test",
      attendance_date: "2026-10-12",
      request_type: "CHECK_IN_ONLY",
      requested_check_in: "2026-10-12T09:15:00Z",
      reason: "Train delay",
      status: "PENDING",
    },
  ]);
  state.policy.mockResolvedValue({ weekly_limit: 1, monthly_limit: 4 });
  state.savePolicy.mockImplementation(async (value) => value);
});

test("filters review requests and displays the pending employee correction", async () => {
  const user = userEvent.setup();
  renderPage();

  expect(await screen.findByText("Avery Lee")).toBeInTheDocument();
  expect(screen.getByText("Train delay")).toBeInTheDocument();
  expect(state.requests).toHaveBeenCalledWith({ status: "PENDING" });

  await user.click(screen.getByRole("combobox", { name: "Status" }));
  await user.click(screen.getByRole("option", { name: "ALL" }));
  await waitFor(() => expect(state.requests).toHaveBeenLastCalledWith({}));
});

test("saves quota limits from the superuser policy form", async () => {
  const user = userEvent.setup();
  renderPage();

  const weekly = await screen.findByRole("spinbutton", { name: "Requests per calendar week" });
  const monthly = screen.getByRole("spinbutton", { name: "Requests per calendar month" });
  await user.clear(weekly);
  await user.type(weekly, "2");
  await user.clear(monthly);
  await user.type(monthly, "6");
  await user.click(screen.getByRole("button", { name: "Save limits" }));

  await waitFor(() =>
    expect(state.savePolicy).toHaveBeenCalledWith({ weekly_limit: 2, monthly_limit: 6 }),
  );
  expect(state.feedback.success).toHaveBeenCalledWith("Quota settings saved successfully.");
  expect(screen.getByText("Current limits: 2 per week · 6 per month")).toBeInTheDocument();
});

test("explains why a signed-in employee cannot review requests", () => {
  state.user = { is_staff: false };
  state.loginType = "employee";
  renderPage();

  expect(
    screen.getByText("You do not have access to review regularization requests."),
  ).toBeInTheDocument();
  expect(state.requests).not.toHaveBeenCalled();
});
