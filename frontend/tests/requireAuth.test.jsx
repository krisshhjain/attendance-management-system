import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
} from "@tanstack/react-router";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, test, expect, vi } from "vitest";
import { server } from "./mocks/server.js";
import { API_BASE_URL } from "../src/lib/api.js";

const authState = vi.hoisted(() => ({ value: null }));
vi.mock("../src/lib/auth.jsx", () => ({ useAuth: () => authState.value }));
vi.mock("../src/components/SuperAdminLayout.jsx", () => ({
  SuperAdminLayout: ({ children }) => <div data-testid="admin-layout">{children}</div>,
}));
vi.mock("../src/components/app/EmployeeLayout.jsx", () => ({
  EmployeeLayout: ({ children }) => <div data-testid="employee-layout">{children}</div>,
}));
vi.mock("../src/components/ForcePasswordChangeModal.jsx", () => ({
  ForcePasswordChangeModal: ({ open }) => (open ? <div>Password change required</div> : null),
}));
vi.mock("../src/components/ShiftSelectionScreen.jsx", () => ({
  ShiftSelectionScreen: ({ onAssigned }) => <button onClick={onAssigned}>Assign my shift</button>,
}));

import { RequireAuth } from "../src/components/RequireAuth.jsx";

function renderProtectedRoute() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const root = createRootRoute({ component: Outlet });
  const attendanceRoute = createRoute({
    getParentRoute: () => root,
    path: "/attendance",
    component: () => (
      <RequireAuth>
        <div>Private attendance records</div>
      </RequireAuth>
    ),
  });
  const loginRoute = createRoute({
    getParentRoute: () => root,
    path: "/login",
    component: () => <div>Sign in to continue</div>,
  });
  const history = createMemoryHistory({ initialEntries: ["/attendance"] });
  const router = createRouter({
    routeTree: root.addChildren([attendanceRoute, loginRoute]),
    history,
    context: { queryClient },
  });

  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return router;
}

beforeEach(() => {
  server.use(
    http.get(`${API_BASE_URL}/attendance/my-shift/`, () =>
      HttpResponse.json({ shift: { id: 4, name: "Day shift" } }),
    ),
  );
});

test("redirects a ready unauthenticated visitor to the login route", async () => {
  authState.value = { ready: true, isAuthenticated: false, user: null, loginType: "employee" };
  const router = renderProtectedRoute();

  expect(await screen.findByText("Sign in to continue")).toBeInTheDocument();
  expect(router.state.location.pathname).toBe("/login");
  expect(screen.queryByText("Private attendance records")).not.toBeInTheDocument();
});

test("blocks an employee whose app access explicitly denies attendance", async () => {
  authState.value = {
    ready: true,
    isAuthenticated: true,
    user: {
      email: "employee@example.test",
      app_access: { attendance: false, dashboard: false, leave: false },
    },
    loginType: "employee",
  };
  const router = renderProtectedRoute();

  expect(
    await screen.findByText(
      "You don't have access to this section. Contact your app administrator.",
    ),
  ).toBeInTheDocument();
  expect(router.state.location.pathname).toBe("/attendance");
  expect(screen.queryByText("Private attendance records")).not.toBeInTheDocument();
});

test("keeps an employee behind shift selection until assignment is confirmed", async () => {
  const user = userEvent.setup();
  server.use(
    http.get(`${API_BASE_URL}/attendance/my-shift/`, () => HttpResponse.json({ shift: null })),
  );
  authState.value = {
    ready: true,
    isAuthenticated: true,
    user: { email: "employee@example.test" },
    loginType: "employee",
  };
  renderProtectedRoute();

  await user.click(await screen.findByRole("button", { name: "Assign my shift" }));
  expect(await screen.findByText("Private attendance records")).toBeInTheDocument();
  expect(screen.getByTestId("employee-layout")).toBeInTheDocument();
});

test("uses the administrator layout and surfaces a required password change", async () => {
  authState.value = {
    ready: true,
    isAuthenticated: true,
    user: { is_superuser: true, must_change_password: true },
    loginType: "admin",
  };
  renderProtectedRoute();

  expect(await screen.findByText("Private attendance records")).toBeInTheDocument();
  expect(screen.getByTestId("admin-layout")).toBeInTheDocument();
  expect(screen.getByText("Password change required")).toBeInTheDocument();
});
