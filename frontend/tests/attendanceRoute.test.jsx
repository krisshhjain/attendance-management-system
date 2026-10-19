import { render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import { Route } from "../src/routes/attendance.jsx";

const state = vi.hoisted(() => ({ user: null, loginType: "employee" }));

vi.mock("@tanstack/react-router", () => ({ createFileRoute: () => (options) => options }));
vi.mock("../src/components/RequireAuth.jsx", () => ({ RequireAuth: ({ children }) => children }));
vi.mock("../src/lib/useAuth.js", () => ({ useAuth: () => state }));
vi.mock("../src/components/admin/AdminAttendancePage.jsx", () => ({
  AdminAttendancePage: ({ allowReset, allowEdit }) => (
    <div data-testid="admin-attendance" data-reset={allowReset} data-edit={allowEdit} />
  ),
}));
vi.mock("../src/components/employee-dashboard/EmployeeAttendancePage.jsx", () => ({
  EmployeeAttendancePage: () => <div>Employee attendance</div>,
}));

beforeEach(() => {
  state.user = null;
  state.loginType = "employee";
});

function renderRoute() {
  const Page = Route.component;
  return render(<Page />);
}

test("gives system administrators full attendance edit access", () => {
  state.loginType = "systemadmin";
  renderRoute();
  expect(screen.getByTestId("admin-attendance")).toHaveAttribute("data-reset", "true");
  expect(screen.getByTestId("admin-attendance")).toHaveAttribute("data-edit", "true");
});

test("limits staff managers to view-only administration", () => {
  state.user = { is_staff: true };
  renderRoute();
  expect(screen.getByTestId("admin-attendance")).toHaveAttribute("data-reset", "false");
  expect(screen.getByTestId("admin-attendance")).toHaveAttribute("data-edit", "false");
});

test("keeps ordinary employees on their own attendance page", () => {
  state.user = { is_staff: false };
  renderRoute();
  expect(screen.getByText("Employee attendance")).toBeInTheDocument();
  expect(screen.queryByTestId("admin-attendance")).not.toBeInTheDocument();
});

test("grants superusers full attendance administration regardless of staff flag", () => {
  state.user = { is_superuser: true, is_staff: false };
  renderRoute();
  expect(screen.getByTestId("admin-attendance")).toHaveAttribute("data-reset", "true");
});
