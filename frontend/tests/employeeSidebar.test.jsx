import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { EmployeeSidebar } from "../src/components/app/EmployeeSidebar.jsx";

const state = vi.hoisted(() => ({
  user: {
    first_name: "Samira",
    designation: "Team Lead",
    app_access: { dashboard: true, attendance: true, leave: true, regularization: false },
  },
  pathname: "/attendance/history",
  logout: vi.fn(),
  navigate: vi.fn(),
  handleDrawerToggle: vi.fn(),
}));

vi.mock("@tanstack/react-router", () => ({
  Link: ({ children, to, onClick, ...props }) => (
    <a
      href={to}
      {...props}
      onClick={(event) => {
        event.preventDefault();
        onClick?.(event);
      }}
    >
      {children}
    </a>
  ),
  useLocation: () => ({ pathname: state.pathname }),
  useNavigate: () => state.navigate,
}));
vi.mock("../src/lib/useAuth.js", () => ({
  useAuth: () => ({ user: state.user, logout: state.logout }),
}));

beforeEach(() => {
  state.user = {
    first_name: "Samira",
    designation: "Team Lead",
    app_access: { dashboard: true, attendance: true, leave: true, regularization: false },
  };
  state.pathname = "/attendance/history";
  state.logout.mockClear();
  state.navigate.mockClear();
  state.handleDrawerToggle.mockClear();
});

test("shows assigned workspace links, marks nested attendance active, and identifies the employee", () => {
  render(<EmployeeSidebar isMobile={false} />);
  const navigation = screen.getByText("Workspace").parentElement.parentElement;
  const attendanceLink = within(navigation).getByRole("link", { name: "My Attendance" });

  expect(attendanceLink).toHaveAttribute("href", "/attendance");
  expect(within(navigation).getByRole("link", { name: "My Leave" })).toBeInTheDocument();
  expect(
    within(navigation).queryByRole("link", { name: "Regularization" }),
  ).not.toBeInTheDocument();
  expect(screen.getByText("Samira")).toBeInTheDocument();
  expect(screen.getByText("Team Lead")).toBeInTheDocument();
});

test("closes the mobile drawer after route selection and logs out to login", async () => {
  const user = userEvent.setup();
  render(<EmployeeSidebar isMobile mobileOpen handleDrawerToggle={state.handleDrawerToggle} />);

  await user.click(screen.getByRole("link", { name: "My Leave" }));
  expect(state.handleDrawerToggle).toHaveBeenCalledOnce();
  await user.click(screen.getByRole("button", { name: "Logout" }));
  expect(state.logout).toHaveBeenCalledOnce();
  expect(state.navigate).toHaveBeenCalledWith({ to: "/login" });
});
