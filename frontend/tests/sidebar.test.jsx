import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { Sidebar } from "../src/components/Sidebar.jsx";

const state = vi.hoisted(() => ({
  user: { email: "lead@example.test", is_superuser: true },
  loginType: "systemadmin",
  pathname: "/administration/regularization/12",
  logout: vi.fn(),
  navigate: vi.fn(),
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
  useAuth: () => ({
    user: state.user,
    loginType: state.loginType,
    logout: state.logout,
  }),
}));

function renderSidebar(props = {}) {
  return render(<Sidebar isMobile={false} {...props} />);
}

beforeEach(() => {
  vi.clearAllMocks();
  state.user = { email: "lead@example.test", is_superuser: true };
  state.loginType = "systemadmin";
  state.pathname = "/administration/regularization/12";
});

test("shows privileged navigation and highlights the active regularization review", () => {
  renderSidebar();

  expect(screen.getByRole("link", { name: "HR Copilot" })).toHaveAttribute("href", "/hr-copilot");
  expect(screen.getByRole("link", { name: "System Logs" })).toHaveAttribute("href", "/system-logs");
  const regularizationLink = screen.getByRole("link", { name: "Regularization" });
  expect(regularizationLink).toHaveAttribute("href", "/admin-regularization");
  expect(regularizationLink.firstChild).toHaveStyle({ backgroundColor: "#eef2ff" });
  expect(screen.getByText("LE")).toBeInTheDocument();
  expect(screen.getByText("System Manager")).toBeInTheDocument();
});

test("limits employee navigation and signs out to the login route", async () => {
  state.user = { email: "employee@example.test", is_staff: false, is_superuser: false };
  state.loginType = "employee";
  state.pathname = "/employees";
  const user = userEvent.setup();
  renderSidebar();

  expect(screen.getByRole("link", { name: "Attendance" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Regularization" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "HR Copilot" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "System Logs" })).not.toBeInTheDocument();
  expect(screen.getByText("Employee")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Logout" }));

  expect(state.logout).toHaveBeenCalledOnce();
  expect(state.navigate).toHaveBeenCalledWith({ to: "/login" });
});

test("closes the temporary drawer after navigation and from its close button", async () => {
  state.pathname = "/dashboard";
  const user = userEvent.setup();
  const handleDrawerToggle = vi.fn();
  renderSidebar({ isMobile: true, mobileOpen: true, handleDrawerToggle });

  const closeButtons = screen.getAllByRole("button", { name: "Close menu" });
  expect(closeButtons).toHaveLength(2);
  await user.click(closeButtons[1]);
  expect(handleDrawerToggle).toHaveBeenCalledOnce();

  await user.click(screen.getByRole("link", { name: "HR Copilot" }));
  expect(handleDrawerToggle).toHaveBeenCalledTimes(2);
  expect(screen.getAllByRole("button", { name: "Close menu" })).toHaveLength(2);
  expect(
    within(screen.getByRole("navigation")).getByRole("link", { name: "Dashboard" }),
  ).toHaveAttribute("href", "/dashboard");
});
