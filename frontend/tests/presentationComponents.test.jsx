import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, test, expect, vi } from "vitest";
import { server } from "./mocks/server.js";
import { API_BASE_URL } from "../src/lib/api.js";
import { EmptyState, ErrorState, LoadingState } from "../src/components/States.jsx";
import { StatusBadge } from "../src/components/StatusBadge.jsx";
import { ChatError } from "../src/components/hr-copilot/ChatError.jsx";
import { ChatMessage } from "../src/components/hr-copilot/ChatMessage.jsx";
import { SummaryCards } from "../src/components/employee-dashboard/SummaryCards.jsx";
import { StatCard } from "../src/components/dashboard/StatCard.jsx";
import { RecentAttendance } from "../src/components/employee-dashboard/RecentAttendance.jsx";

vi.mock("@tanstack/react-router", () => ({
  Link: ({ to, children, ...props }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));

beforeEach(() => {
  vi.clearAllMocks();
});

test("renders loading, recoverable error, and empty attendance states", async () => {
  const retry = vi.fn();
  render(
    <>
      <LoadingState message="Loading employee records..." />
      <ErrorState message="Attendance is unavailable." onRetry={retry} />
      <EmptyState message="No rows match these filters." />
    </>,
  );

  expect(screen.getByText("Loading employee records...")).toBeInTheDocument();
  expect(screen.getByText("Attendance is unavailable.")).toBeInTheDocument();
  expect(screen.getByText("No rows match these filters.")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(retry).toHaveBeenCalledOnce();
});

test("shows known and unknown attendance status labels", () => {
  const { rerender } = render(<StatusBadge status="CHECKED_IN" />);
  expect(screen.getByText("Checked In")).toBeInTheDocument();
  rerender(<StatusBadge status="WAITING_FOR_APPROVAL" />);
  expect(screen.getByText("WAITING FOR APPROVAL")).toBeInTheDocument();
});

test("shows copilot errors and renders query results with null values", () => {
  const { rerender } = render(<ChatError />);
  expect(screen.getByRole("alert")).toHaveTextContent("Something went wrong");
  rerender(<ChatError message="The report could not be loaded." />);
  expect(screen.getByRole("alert")).toHaveTextContent("The report could not be loaded.");

  rerender(
    <ChatMessage
      message={{
        id: "answer-1",
        role: "assistant",
        content: "Two employees matched.",
        data: {
          columns: ["employee_name", "status"],
          rows: [{ employee_name: "Alice", status: "PRESENT" }],
        },
      }}
    />,
  );
  expect(screen.getByRole("table", { name: "HR Copilot query results" })).toBeInTheDocument();
  expect(screen.getByText("employee name")).toBeInTheDocument();
  expect(screen.getByText("Alice")).toBeInTheDocument();
  expect(screen.getByText("PRESENT")).toBeInTheDocument();
});

test("lets a manager approve a pending HR Copilot action and prevents duplicate action clicks", async () => {
  const onAction = vi.fn();
  const user = userEvent.setup();
  const message = {
    id: "answer-2",
    role: "assistant",
    pendingAction: {
      action_id: "action-9",
      action_type: "leave.create",
      status: "PENDING",
      target_data: {
        employee_name: "Alice Employee",
        start_date: "2026-01-28",
        reason: "Family event",
      },
      proposed_changes: { status: "PENDING" },
      warning_message: "Confirm the leave dates before approval.",
    },
  };
  const { rerender } = render(<ChatMessage message={message} onAction={onAction} />);

  expect(screen.getByText("Leave Request")).toBeInTheDocument();
  expect(screen.getByText("Alice Employee")).toBeInTheDocument();
  expect(screen.getByText("Confirm the leave dates before approval.")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Approve change" }));
  expect(onAction).toHaveBeenCalledWith("action-9", "approve");

  rerender(<ChatMessage message={message} onAction={onAction} busyActionId="action-9" />);
  expect(screen.getByRole("button", { name: "Working…" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
});

test("shows the correct employee attendance summary for active and completed days", () => {
  const { rerender } = render(
    <SummaryCards
      data={{
        status: "CHECKED_IN",
        check_in: "2026-01-26T09:00:00Z",
        working_duration: "02:00:00",
      }}
    />,
  );
  expect(screen.getByText("Present (In Progress)")).toBeInTheDocument();
  expect(screen.getByText("Elapsed Time")).toBeInTheDocument();
  rerender(
    <SummaryCards
      data={{
        status: "COMPLETED",
        check_in: null,
        check_out: "2026-01-26T17:00:00Z",
        working_duration: "08:00:00",
      }}
    />,
  );
  expect(screen.getByText("Checked Out")).toBeInTheDocument();
  expect(screen.getByText("Working Duration")).toBeInTheDocument();
  expect(screen.getByText("--:--")).toBeInTheDocument();
});

test("renders a dashboard statistic and its optional subtitle", () => {
  render(<StatCard title="Employees present" value={12} subtitle="Today" colorClass="success" />);
  expect(screen.getByText("Employees present")).toBeInTheDocument();
  expect(screen.getByText("12")).toBeInTheDocument();
  expect(screen.getByText("Today")).toBeInTheDocument();
});

test("loads the latest five attendance rows in descending date order", async () => {
  server.use(
    http.get(`${API_BASE_URL}/attendance/history/`, () =>
      HttpResponse.json(
        Array.from({ length: 7 }, (_, index) => ({
          id: index,
          date: `2026-01-${String(index + 1).padStart(2, "0")}`,
          status: "PRESENT",
          working_duration: "08:00:00",
        })),
      ),
    ),
  );
  render(<RecentAttendance />);

  const table = await screen.findByRole("table");
  const rows = within(table).getAllByRole("row");
  expect(rows).toHaveLength(6);
  expect(rows[1]).toHaveTextContent("Jan 7, 2026");
  expect(rows[5]).toHaveTextContent("Jan 3, 2026");
  expect(screen.getByRole("link", { name: "View all" })).toHaveAttribute("href", "/attendance");
});

test("shows an empty dashboard state when recent attendance cannot be loaded", async () => {
  server.use(
    http.get(`${API_BASE_URL}/attendance/history/`, () =>
      HttpResponse.json({ detail: "Unavailable" }, { status: 503 }),
    ),
  );
  render(<RecentAttendance />);
  expect(await screen.findByText("No recent attendance found.")).toBeInTheDocument();
});
