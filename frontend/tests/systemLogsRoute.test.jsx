import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { Route } from "../src/routes/system-logs.jsx";
import { API_BASE_URL } from "../src/lib/api.js";
import { server } from "./mocks/server.js";

const state = vi.hoisted(() => ({
  user: { is_superuser: true },
  search: {
    search: "",
    category: "",
    event_type: "",
    severity: "",
    status: "",
    source: "",
    actor: "",
    actor_role: "",
    date_from: "",
    date_to: "",
    page: 1,
    page_size: 50,
  },
  navigate: vi.fn(),
  success: vi.fn(),
  notifyError: vi.fn(),
}));

vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (options) => ({
    ...options,
    useSearch: () => state.search,
    useNavigate: () => state.navigate,
  }),
}));
vi.mock("../src/components/RequireAuth.jsx", () => ({ RequireAuth: ({ children }) => children }));
vi.mock("../src/lib/auth.jsx", () => ({ useAuth: () => ({ user: state.user }) }));
vi.mock("../src/feedback/FeedbackProvider.jsx", () => ({
  useFeedback: () => ({ success: state.success, notifyError: state.notifyError }),
}));

const record = {
  id: 41,
  timestamp: "2026-10-12T09:30:00Z",
  severity: "ERROR",
  category: "AUTHENTICATION",
  event_type: "LOGIN_FAILED",
  actor: { name: "Avery Lee", email: "avery@example.test" },
  actor_role: "EMPLOYEE",
  target_label: "Avery Lee",
  target_id: "emp-4",
  status: "FAILED",
  source: "API",
  message: "Invalid credentials",
  request_id: "req-41",
  ip_address: "192.0.2.4",
  user_agent: "Dailoqa test client",
  before_state: null,
  after_state: { attempts: 1 },
  metadata: "authentication failure",
};

function renderPage() {
  const Component = Route.component;
  return render(<Component />);
}

beforeEach(() => {
  vi.clearAllMocks();
  state.user = { is_superuser: true };
  state.search = {
    search: "",
    category: "",
    event_type: "",
    severity: "",
    status: "",
    source: "",
    actor: "",
    actor_role: "",
    date_from: "",
    date_to: "",
    page: 1,
    page_size: 50,
  };
  server.use(
    http.get(`${API_BASE_URL}/system-logs/actors/`, () => HttpResponse.json([])),
    http.get(`${API_BASE_URL}/system-logs/`, () =>
      HttpResponse.json({ count: 1, next: null, previous: null, results: [record] }),
    ),
  );
});

test("normalizes URL filters and pagination to safe defaults", () => {
  expect(
    Route.validateSearch({
      search: 42,
      category: "SECURITY",
      page: "-4",
      page_size: "500",
      status: null,
    }),
  ).toEqual({
    search: "",
    category: "SECURITY",
    event_type: "",
    severity: "",
    status: "",
    source: "",
    actor: "",
    actor_role: "",
    date_from: "",
    date_to: "",
    page: 1,
    page_size: 100,
  });
});

test("protects the audit log page from non-superusers", () => {
  state.user = { is_superuser: false };
  renderPage();
  expect(screen.getByText("You do not have access to System Logs.")).toBeInTheDocument();
});

test("filters audit events and opens full security details", async () => {
  const user = userEvent.setup();
  let requestedUrl;
  server.use(
    http.get(`${API_BASE_URL}/system-logs/`, ({ request }) => {
      requestedUrl = request.url;
      return HttpResponse.json({ count: 1, results: [record] });
    }),
  );
  renderPage();

  const eventRow = await screen.findByRole("row", { name: /LOGIN_FAILED/ });
  expect(within(eventRow).getByText("Invalid credentials")).toBeInTheDocument();
  await user.click(eventRow);
  expect(await screen.findByText("Log #41")).toBeInTheDocument();
  expect(screen.getByText("req-41")).toBeInTheDocument();
  expect(
    screen.getByText(
      (_, element) => element.tagName === "PRE" && element.textContent.includes('"attempts": 1'),
    ),
  ).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Close log details" }));
  await user.click(screen.getByRole("combobox", { name: "Category" }));
  await user.click(screen.getByRole("option", { name: "SECURITY" }));
  const navigation = state.navigate.mock.calls.at(-1)[0];
  expect(navigation.search(state.search)).toMatchObject({ category: "SECURITY", page: 1 });
  expect(new URL(requestedUrl).searchParams.get("page_size")).toBe("50");
});

test("retries a failed log query and supports clearing active filters", async () => {
  const user = userEvent.setup();
  let shouldFail = true;
  server.use(
    http.get(`${API_BASE_URL}/system-logs/`, () => {
      if (shouldFail)
        return HttpResponse.json({ detail: "Audit service unavailable" }, { status: 503 });
      return HttpResponse.json({ count: 0, results: [] });
    }),
  );
  state.search.severity = "CRITICAL";
  renderPage();

  expect(await screen.findByText("Audit service unavailable")).toBeInTheDocument();
  shouldFail = false;
  await user.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByText("No logs match the current filters.")).toBeInTheDocument();
  expect(screen.getAllByText("CRITICAL").length).toBeGreaterThan(0);
  await user.click(screen.getByRole("button", { name: "Reset Filters" }));
  expect(state.navigate).toHaveBeenCalledWith({ search: {} });
});

test("downloads a CSV export and reports an export failure", async () => {
  const user = userEvent.setup();
  const createObjectURL = vi.fn(() => "blob:system-logs");
  const revokeObjectURL = vi.fn();
  const NativeURL = globalThis.URL;
  vi.stubGlobal(
    "URL",
    class TestURL extends NativeURL {
      static createObjectURL = createObjectURL;
      static revokeObjectURL = revokeObjectURL;
    },
  );
  const clickDownload = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  let exportUrl;
  server.use(
    http.get(`${API_BASE_URL}/system-logs/export/`, ({ request }) => {
      exportUrl = request.url;
      return new HttpResponse("timestamp,event_type\\n2026-10-12,LOGIN_FAILED", {
        headers: { "Content-Type": "text/csv" },
      });
    }),
  );
  renderPage();
  await user.click(screen.getByRole("button", { name: "CSV" }));

  await waitFor(() =>
    expect(state.success).toHaveBeenCalledWith("System logs exported successfully."),
  );
  expect(new URLSearchParams(new URL(exportUrl).search).get("export_format")).toBe("csv");
  expect(createObjectURL).toHaveBeenCalledOnce();
  expect(clickDownload).toHaveBeenCalledOnce();
  expect(revokeObjectURL).toHaveBeenCalledWith("blob:system-logs");

  server.use(
    http.get(`${API_BASE_URL}/system-logs/export/`, () =>
      HttpResponse.json({ detail: "Export service is unavailable." }, { status: 503 }),
    ),
  );
  await user.click(screen.getByRole("button", { name: "Excel" }));
  await waitFor(() =>
    expect(state.notifyError).toHaveBeenCalledWith(
      expect.objectContaining({
        message: "Export service is unavailable.",
      }),
      expect.objectContaining({
        title: "Export failed",
        fallback: "The system logs could not be exported.",
      }),
    ),
  );
});

test("deletes logs through the chosen date and refreshes the current query", async () => {
  const user = userEvent.setup();
  let deleteUrl;
  server.use(
    http.delete(`${API_BASE_URL}/system-logs/`, ({ request }) => {
      deleteUrl = request.url;
      return new HttpResponse(null, { status: 204 });
    }),
  );
  renderPage();
  await screen.findByRole("row", { name: /LOGIN_FAILED/ });
  await user.click(screen.getByRole("button", { name: "Delete Logs" }));
  const dialog = screen.getByRole("dialog");
  await user.type(within(dialog).getByLabelText("Delete logs until"), "2026-10-01");
  await user.click(within(dialog).getByRole("button", { name: "Delete Logs" }));

  await waitFor(() => expect(state.success).toHaveBeenCalledWith("Logs deleted successfully."));
  expect(new URL(deleteUrl).searchParams.get("until_date")).toBe("2026-10-01");
  await waitFor(() =>
    expect(screen.getByRole("row", { name: /LOGIN_FAILED/ })).toBeInTheDocument(),
  );
});
