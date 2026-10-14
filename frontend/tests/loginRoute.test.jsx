import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { Route } from "../src/routes/login.jsx";
import { Route as AdminLoginRoute } from "../src/routes/admin-login.jsx";
import { Route as SystemManagerLoginRoute } from "../src/routes/systemadmin-login.jsx";

const state = vi.hoisted(() => ({
  login: vi.fn(),
  navigate: vi.fn(),
  isAuthenticated: false,
  ready: true,
  loginType: "employee",
}));

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (options) => options,
  useNavigate: () => state.navigate,
}));
vi.mock("../src/lib/auth.jsx", () => ({
  useAuth: () => ({
    login: state.login,
    isAuthenticated: state.isAuthenticated,
    ready: state.ready,
    loginType: state.loginType,
  }),
}));

function renderPage(route = Route) {
  const Component = route.component;
  return render(<Component />);
}

beforeEach(() => {
  vi.clearAllMocks();
  state.login.mockResolvedValue(undefined);
  state.isAuthenticated = false;
  state.ready = true;
  state.loginType = "employee";
});

test("submits trimmed credentials for the selected system manager account", async () => {
  const user = userEvent.setup();
  renderPage();

  await user.click(screen.getByRole("button", { name: "System manager" }));
  await user.type(screen.getByRole("textbox", { name: "Email" }), "  lead@example.test  ");
  await user.type(
    document.querySelector('input[autocomplete="current-password"]'),
    "secret-password",
  );
  await user.click(screen.getByRole("button", { name: "Sign in", exact: true }));

  expect(state.login).toHaveBeenCalledWith("lead@example.test", "secret-password", "systemadmin");
  expect(state.navigate).toHaveBeenCalledWith({ to: "/dashboard", replace: true });
});

test("shows login failures and lets the user reveal the password", async () => {
  state.login.mockRejectedValueOnce(new Error("Invalid company credentials"));
  const user = userEvent.setup();
  renderPage();

  const password = document.querySelector('input[autocomplete="current-password"]');
  await user.type(screen.getByRole("textbox", { name: "Email" }), "employee@example.test");
  await user.type(password, "incorrect-password");
  await user.click(screen.getByRole("button", { name: "Show" }));
  expect(password).toHaveAttribute("type", "text");
  await user.click(screen.getByRole("button", { name: "Sign in", exact: true }));

  expect(await screen.findByText("Invalid company credentials")).toBeInTheDocument();
  expect(state.navigate).not.toHaveBeenCalled();
});

test("redirects a ready authenticated user to the dashboard", () => {
  state.isAuthenticated = true;
  renderPage();
  expect(state.navigate).toHaveBeenCalledWith({ to: "/dashboard", replace: true });
});

test.each([
  ["admin", AdminLoginRoute, "Admin Sign in", "admin"],
  ["system manager", SystemManagerLoginRoute, "System Manager Sign in", "systemadmin"],
])(
  "signs in through the %s login route with the correct authorization role",
  async (_label, route, heading, role) => {
    const user = userEvent.setup();
    renderPage(route);

    expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "Email" }), "  admin@example.test  ");
    await user.type(
      document.querySelector('input[autocomplete="current-password"]'),
      "manager-password",
    );
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(state.login).toHaveBeenCalledWith("admin@example.test", "manager-password", role);
    expect(state.navigate).toHaveBeenCalledWith({ to: "/dashboard", replace: true });
  },
  15_000,
);
