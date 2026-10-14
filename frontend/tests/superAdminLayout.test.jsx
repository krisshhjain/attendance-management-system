import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { SuperAdminLayout } from "../src/components/SuperAdminLayout.jsx";

const state = vi.hoisted(() => ({
  user: { email: "admin@example.com" },
  loginType: "admin",
  logout: vi.fn(),
  navigate: vi.fn(),
}));

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => state.navigate,
}));
vi.mock("../src/lib/auth.jsx", () => ({
  useAuth: () => ({ user: state.user, loginType: state.loginType, logout: state.logout }),
}));
vi.mock("../src/components/Sidebar.jsx", () => ({
  Sidebar: ({ isMobile, mobileOpen, handleDrawerToggle }) => (
    <div data-testid="sidebar" data-mobile={isMobile} data-open={mobileOpen}>
      <button onClick={handleDrawerToggle}>Toggle sidebar</button>
    </div>
  ),
}));
vi.mock("../src/components/notifications/NotificationBell.jsx", () => ({
  NotificationBell: () => <button>Notifications</button>,
}));
vi.mock("../src/components/SystemAdminChatWidget.jsx", () => ({
  SystemAdminChatWidget: () => <div>System manager support</div>,
}));

beforeEach(() => {
  state.user = { email: "admin@example.com" };
  state.loginType = "admin";
  state.logout.mockClear();
  state.navigate.mockClear();
  window.innerWidth = 1200;
});

test("opens profile actions, navigates to settings, and closes the menu on outside click", async () => {
  const user = userEvent.setup();
  render(
    <SuperAdminLayout title="People">
      <p>People page content</p>
    </SuperAdminLayout>,
  );

  expect(screen.getByRole("heading", { name: "People" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /ad admin/i })).toBeInTheDocument();
  expect(screen.getByText("People page content")).toBeInTheDocument();
  const profile = screen.getByRole("button", { name: /ad admin/i });
  await user.click(profile);
  expect(screen.getByText("admin@example.com")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Settings" }));
  expect(state.navigate).toHaveBeenCalledWith({ to: "/settings" });
  expect(screen.queryByRole("button", { name: "Log Out" })).not.toBeInTheDocument();

  await user.click(profile);
  fireEvent.mouseDown(document.body);
  await waitFor(() =>
    expect(screen.queryByRole("button", { name: "Log Out" })).not.toBeInTheDocument(),
  );
});

test("logs out to login, adapts the header to mobile, and shows manager support by role", async () => {
  state.user = null;
  state.loginType = "systemadmin";
  window.innerWidth = 700;
  const user = userEvent.setup();
  render(<SuperAdminLayout />);

  expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
  expect(screen.getByTestId("sidebar")).toHaveAttribute("data-mobile", "true");
  expect(screen.getByText("System manager support")).toBeInTheDocument();
  expect(screen.queryByText("Super Admin")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Open navigation" }));
  expect(screen.getByTestId("sidebar")).toHaveAttribute("data-open", "true");
  await user.click(screen.getByRole("button", { name: /su/i }));
  await user.click(screen.getByRole("button", { name: "Log Out" }));
  expect(state.logout).toHaveBeenCalledOnce();
  expect(state.navigate).toHaveBeenCalledWith({ to: "/login" });
});

test("updates its responsive mode when the viewport crosses the desktop breakpoint", () => {
  render(<SuperAdminLayout />);
  expect(screen.getByTestId("sidebar")).toHaveAttribute("data-mobile", "false");
  window.innerWidth = 800;
  fireEvent(window, new Event("resize"));
  expect(screen.getByTestId("sidebar")).toHaveAttribute("data-mobile", "true");
});
