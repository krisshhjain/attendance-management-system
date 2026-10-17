import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, expect, test, vi } from "vitest";
import { API_BASE_URL } from "../src/lib/api.js";
import { Route } from "../src/routes/hr-copilot.jsx";
import { server } from "./mocks/server.js";

const state = vi.hoisted(() => ({
  loginType: "systemadmin",
  user: { id: 8, email: "sam@example.test" },
  selectedScope: { brId: 3, orgId: 2 },
  success: vi.fn(),
  notifyError: vi.fn(),
}));

vi.mock("@tanstack/react-router", () => ({ createFileRoute: () => (options) => options }));
vi.mock("../src/components/RequireAuth.jsx", () => ({ RequireAuth: ({ children }) => children }));
vi.mock("../src/lib/useAuth.js", () => ({
  useAuth: () => ({ loginType: state.loginType, user: state.user }),
}));
vi.mock("../src/lib/useOrganizationScope.js", () => ({
  useOrganizationScope: () => ({ selectedScope: state.selectedScope }),
}));
vi.mock("../src/feedback/useFeedback.js", () => ({
  useFeedback: () => ({ success: state.success, notifyError: state.notifyError }),
}));

function renderPage() {
  const Component = Route.component;
  return render(<Component />);
}

beforeEach(() => {
  state.loginType = "systemadmin";
  state.user = { id: 8, email: "sam@example.test" };
  state.selectedScope = { brId: 3, orgId: 2 };
  vi.clearAllMocks();
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
    configurable: true,
    value: vi.fn(),
  });
});

test("system managers send scoped HR questions and see the response", async () => {
  let requestBody;
  server.use(
    http.post(`${API_BASE_URL}/hr-copilot/query/`, async ({ request }) => {
      requestBody = await request.json();
      return HttpResponse.json({
        conversation_id: "conversation-17",
        answer: "Two leave requests are awaiting review.",
        data: { count: 2 },
      });
    }),
  );
  const user = userEvent.setup();
  renderPage();
  await user.type(
    screen.getByPlaceholderText("Ask HR Copilot something..."),
    "Which leave requests are pending?",
  );
  await user.click(screen.getByRole("button", { name: "Send message" }));

  expect(await screen.findByText("Two leave requests are awaiting review.")).toBeInTheDocument();
  expect(requestBody).toEqual({
    message: "Which leave requests are pending?",
    conversation_id: expect.any(String),
    scope: { brId: 3, orgId: 2 },
  });
  expect(sessionStorage.getItem("hr-copilot-current-8")).toBe("conversation-17");
}, 15_000);

test("restores a pending approval and confirms its completion", async () => {
  sessionStorage.setItem("hr-copilot-current-8", "saved-conversation");
  server.use(
    http.get(`${API_BASE_URL}/hr-copilot/conversations/saved-conversation/`, () =>
      HttpResponse.json({
        messages: [
          {
            id: "assistant-1",
            role: "assistant",
            content: "A leave request is ready for approval.",
            pending_action: { action_id: "action-5", status: "PENDING" },
          },
        ],
      }),
    ),
    http.post(`${API_BASE_URL}/hr-copilot/actions/approve/`, async ({ request }) => {
      expect(await request.json()).toEqual({
        action_id: "action-5",
        action: "approve",
        conversation_id: "saved-conversation",
      });
      return HttpResponse.json({ answer: "Leave approved." });
    }),
  );
  const user = userEvent.setup();
  renderPage();
  expect(await screen.findByText("A leave request is ready for approval.")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Approve change" }));
  await waitFor(() => expect(state.success).toHaveBeenCalledWith("Action completed successfully."));
  expect(await screen.findByText("Leave approved.")).toBeInTheDocument();
}, 15_000);

test("blocks HR Copilot for non system managers", () => {
  state.loginType = "admin";
  renderPage();
  expect(screen.getByText("System Manager access is required.")).toBeInTheDocument();
  expect(screen.queryByPlaceholderText("Ask HR Copilot something...")).not.toBeInTheDocument();
});

test("restores and cancels a pending approval while preserving its response", async () => {
  sessionStorage.setItem("hr-copilot-current-8", "pending-conversation");
  server.use(
    http.get(`${API_BASE_URL}/hr-copilot/conversations/pending-conversation/`, () =>
      HttpResponse.json({
        messages: [
          {
            id: "assistant-pending",
            role: "assistant",
            content: "A correction is ready for review.",
            pending_action: {
              action_id: "action-cancel",
              status: "PENDING",
              action_type: "attendance_correction",
              target_data: { employee_name: "Avery Lee", date: "2026-10-12" },
              proposed_changes: { status: "PRESENT" },
            },
          },
        ],
      }),
    ),
    http.post(`${API_BASE_URL}/hr-copilot/actions/approve/`, async ({ request }) => {
      expect(await request.json()).toEqual({
        action_id: "action-cancel",
        action: "cancel",
        conversation_id: "pending-conversation",
      });
      return HttpResponse.json({});
    }),
  );
  const user = userEvent.setup();
  renderPage();

  expect(await screen.findByText("A correction is ready for review.")).toBeInTheDocument();
  expect(screen.getByText("Avery Lee")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Cancel", exact: true }));

  expect(await screen.findByText("Cancelled · no changes made")).toBeInTheDocument();
  expect(screen.getByText("A correction is ready for review.")).toBeInTheDocument();
  expect(state.success).toHaveBeenCalledWith("Action cancelled successfully.");
}, 15_000);

test("shows a recoverable error when the HR assistant request is rejected", async () => {
  server.use(
    http.post(`${API_BASE_URL}/hr-copilot/query/`, () =>
      HttpResponse.json({ detail: "HR records are temporarily unavailable." }, { status: 503 }),
    ),
  );
  const user = userEvent.setup();
  renderPage();
  await user.type(
    screen.getByPlaceholderText("Ask HR Copilot something..."),
    "Show my leave balance",
  );
  await user.click(screen.getByRole("button", { name: "Send message" }));

  expect(await screen.findByText("HR records are temporarily unavailable.")).toBeInTheDocument();
  expect(screen.getByText("Show my leave balance")).toBeInTheDocument();
}, 15_000);
