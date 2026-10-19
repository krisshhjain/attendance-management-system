import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { Route } from "../src/routes/my-team.jsx";
import { API_BASE_URL } from "../src/lib/api.js";
import { server } from "./mocks/server.js";

const state = vi.hoisted(() => ({ queryResult: null }));
vi.mock("@tanstack/react-router", () => ({ createFileRoute: () => (options) => options }));
vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, useQuery: (...args) => state.queryResult ?? actual.useQuery(...args) };
});
vi.mock("../src/components/RequireAuth.jsx", () => ({ RequireAuth: ({ children }) => children }));

const members = [
  {
    id: 1,
    name: "Avery Lee",
    status: "CHECKED_IN",
    subsection: "A1",
    check_in_time: "2026-10-14T09:05:00Z",
  },
  { id: 2, name: "Morgan Chen", status: "YET_TO_CHECK_IN", subsection: "A2" },
  { id: 3, name: "Jordan Patel", status: "WEEKEND" },
  { id: 4, name: "Samira Khan", status: "ON_LEAVE", leave_type: "Annual Leave" },
  { id: 5, name: "Noah Diaz", status: "HOLIDAY", holiday_name: "Founders Day" },
];

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  const Component = Route.component;
  return render(
    <QueryClientProvider client={queryClient}>
      <Component />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  state.queryResult = null;
  server.use(
    http.get(`${API_BASE_URL}/attendance/my-team/`, () =>
      HttpResponse.json({
        team_employment_type: "FULL_TIME",
        team_section: "A",
        current_user_id: 1,
        checked_in_count: 1,
        yet_to_check_in_count: 2,
        on_leave_count: 1,
        holiday_count: 0,
        members,
      }),
    ),
  );
});

test("groups current team members by attendance state and marks the signed-in manager", async () => {
  renderPage();

  expect(await screen.findByText("Avery Lee")).toBeInTheDocument();
  expect(screen.getByText(/FULL_TIME/)).toBeInTheDocument();
  expect(screen.getByText(/Section A/)).toBeInTheDocument();
  expect(screen.getByText("You")).toBeInTheDocument();
  expect(screen.getByText("Avery Lee").parentElement.parentElement).toHaveTextContent(/(AM|PM)/);
  expect(screen.getByText("Morgan Chen")).toBeInTheDocument();
  expect(screen.getByText("Jordan Patel")).toBeInTheDocument();
  expect(screen.getByText("Weekend")).toBeInTheDocument();
  expect(screen.getByText("Samira Khan")).toBeInTheDocument();
  expect(screen.getByText("Annual Leave")).toBeInTheDocument();
  expect(screen.getByText("Noah Diaz")).toBeInTheDocument();
  expect(screen.getByText("Founders Day")).toBeInTheDocument();
  expect(screen.getAllByText("Yet to check in")[0].parentElement).toHaveTextContent("2");
});

test("explains a team configuration note from the server", async () => {
  server.use(
    http.get(`${API_BASE_URL}/attendance/my-team/`, () =>
      HttpResponse.json({ members: [], note: "No team is assigned." }),
    ),
  );
  renderPage();

  expect(await screen.findByText(/No team is assigned/)).toBeInTheDocument();
  expect(screen.getAllByText("No members")).toHaveLength(4);
});

test("shows the API error so managers can distinguish a failed team request", async () => {
  state.queryResult = {
    data: undefined,
    isLoading: false,
    isError: true,
    error: new Error("Team attendance is unavailable."),
  };
  renderPage();

  expect(screen.getByText("Team attendance is unavailable.")).toBeInTheDocument();
  expect(screen.queryByText("Avery Lee")).not.toBeInTheDocument();
});
