import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, expect, test, vi } from "vitest";
import { API_BASE_URL } from "../src/lib/api.js";
import { OrganizationScopeProvider } from "../src/lib/organizationScope.jsx";
import { Route } from "../src/routes/dashboard.jsx";
import { server } from "./mocks/server.js";

const state = vi.hoisted(() => ({
  user: {
    is_superuser: true,
    organizational_scope: { assignedBRs: [{ id: 5, name: "North" }] },
  },
  loginType: "systemadmin",
}));

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (options) => options,
  useNavigate: () => vi.fn(),
}));
vi.mock("../src/components/RequireAuth.jsx", () => ({ RequireAuth: ({ children }) => children }));
vi.mock("../src/lib/auth.jsx", () => ({
  useAuth: () => ({ user: state.user, loginType: state.loginType }),
}));
vi.mock("../src/components/dashboard/AttendanceChart.jsx", () => ({
  AttendanceChart: ({ data }) => <div>Chart reports {data?.present_today ?? 0} present</div>,
}));
vi.mock("../src/components/dashboard/WeeklyTrendChart.jsx", () => ({
  WeeklyTrendChart: () => <div>Weekly trend</div>,
}));
vi.mock("../src/components/dashboard/UpcomingLeaves.jsx", () => ({
  UpcomingLeaves: () => <div>Upcoming leave list</div>,
}));
vi.mock("../src/components/dashboard/LatestAttendanceTable.jsx", () => ({
  LatestAttendanceTable: ({ records }) => <div>Latest rows: {records.length}</div>,
}));

const employees = [
  {
    id: 1,
    user: { first_name: "Avery", last_name: "Lee", email: "avery@example.test" },
    is_active: true,
  },
  { id: 2, user: { first_name: "Blake", email: "blake@example.test" }, is_active: true },
  { id: 3, email: "casey@example.test", is_active: true },
  { id: 4, user: { email: "dana@example.test" }, is_active: false },
];

function setDashboardHandlers({ workingDay = true } = {}) {
  server.use(
    http.get(`${API_BASE_URL}/admin/dashboard/`, () =>
      HttpResponse.json({
        is_working_day: workingDay,
        attendance: [
          {
            employee: "avery@example.test",
            employee_name: "Avery Lee",
            status: "PRESENT",
            check_in: "2026-10-14T09:00:00Z",
            check_out: "2026-10-14T17:00:00Z",
          },
          {
            employee: "blake@example.test",
            status: "INCOMPLETE",
            check_in: "2026-10-14T09:00:00Z",
            check_out: null,
          },
          { employee: "casey@example.test", status: "LEAVE" },
        ],
      }),
    ),
    http.get(`${API_BASE_URL}/admin/employees/list/`, () => HttpResponse.json(employees)),
  );
}

function renderDashboard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Component = Route.component;
  return render(
    <QueryClientProvider client={queryClient}>
      <OrganizationScopeProvider>
        <Component />
      </OrganizationScopeProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  state.loginType = "systemadmin";
  state.user = {
    is_superuser: true,
    organizational_scope: { assignedBRs: [{ id: 5, name: "North" }] },
  };
});

test("shows scoped attendance totals and opens the present employee list", async () => {
  setDashboardHandlers();
  const user = userEvent.setup();
  renderDashboard();

  expect(await screen.findByText("Overview")).toBeInTheDocument();
  const presentCard = screen.getByText("Present Today").closest(".MuiPaper-root");
  await waitFor(() => expect(presentCard).toHaveTextContent("1"));
  await user.click(screen.getByText("Present Today"));
  const dialog = screen.getByRole("dialog");
  expect(within(dialog).getByText("Present Today")).toBeInTheDocument();
  expect(within(dialog).getByText("Avery Lee")).toBeInTheDocument();
});

test("reports zero absences on nonworking days", async () => {
  setDashboardHandlers({ workingDay: false });
  renderDashboard();

  expect(await screen.findByText("Overview")).toBeInTheDocument();
  const absentCard = screen.getByText("Absent Today").closest(".MuiPaper-root");
  await waitFor(() => expect(absentCard).toHaveTextContent("0"));
  await userEvent.setup().click(screen.getByText("Absent Today"));
  expect(screen.getByText("No employees found in this category.")).toBeInTheDocument();
});

test("keeps the dashboard usable when attendance data is unavailable", async () => {
  server.use(
    http.get(`${API_BASE_URL}/admin/dashboard/`, () =>
      HttpResponse.json({ detail: "Dashboard service unavailable." }, { status: 503 }),
    ),
    http.get(`${API_BASE_URL}/admin/employees/list/`, () => HttpResponse.json(employees)),
  );
  renderDashboard();
  expect(await screen.findByText("Overview")).toBeInTheDocument();
  expect(screen.getByText("Chart reports 0 present")).toBeInTheDocument();
  const presentCard = screen.getByText("Present Today").closest(".MuiPaper-root");
  await waitFor(() => expect(presentCard).toHaveTextContent("0"));
}, 15_000);
