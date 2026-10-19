import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { LatestAttendanceTable } from "../src/components/dashboard/LatestAttendanceTable.jsx";
import { QuickActions } from "../src/components/employee-dashboard/QuickActions.jsx";
import { WelcomeHeader } from "../src/components/employee-dashboard/WelcomeHeader.jsx";

const state = vi.hoisted(() => ({
  navigate: vi.fn(),
  user: null,
}));

vi.mock("@tanstack/react-router", () => ({
  Link: ({ to, children, ...props }) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
  useNavigate: () => state.navigate,
}));
vi.mock("../src/lib/useAuth.js", () => ({ useAuth: () => ({ user: state.user }) }));

beforeEach(() => {
  state.navigate.mockClear();
});

afterEach(() => vi.useRealTimers());

test("orders attendance by newest check-in, omits missing check-ins, and caps the table at ten", () => {
  const records = [
    { employee: "No check-in", check_in: null, status: "ABSENT" },
    ...Array.from({ length: 11 }, (_, index) => ({
      employee: `Employee ${index}`,
      employee_name: `Employee ${index}`,
      section: index === 10 ? null : "Operations",
      status: "PRESENT",
      check_in: `2026-10-${String(index + 1).padStart(2, "0")}T09:00:00`,
      working_duration: "08:00:00",
    })),
  ];
  render(<LatestAttendanceTable records={records} />);

  const rows = screen.getAllByRole("row");
  expect(rows).toHaveLength(11);
  expect(within(rows[1]).getByText("Employee 10")).toBeInTheDocument();
  expect(screen.queryByText("Employee 0")).not.toBeInTheDocument();
  expect(screen.queryByText("No check-in")).not.toBeInTheDocument();
  expect(within(rows[1]).getByText("---")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "View All Attendance" })).toHaveAttribute(
    "href",
    "/attendance",
  );
});

test("shows a useful empty state when there are no check-ins", () => {
  render(<LatestAttendanceTable records={[{ employee: "Not checked in", check_in: null }]} />);
  expect(screen.getByText("No attendance records found for today.")).toBeInTheDocument();
});

test("routes dashboard quick actions to attendance, leave and settings", async () => {
  const user = userEvent.setup();
  render(<QuickActions />);

  await user.click(screen.getByText("View Attendance"));
  await user.click(screen.getByText("Apply for Leave"));
  await user.click(screen.getByText("Settings"));
  expect(state.navigate.mock.calls).toEqual([
    [{ to: "/attendance" }],
    [{ to: "/leave" }],
    [{ to: "/settings" }],
  ]);
});

test("greets the employee using their profile name and current local time", () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date(2026, 9, 14, 9, 30));
  state.user = { name: "morgan lee", email: "morgan@example.test" };
  render(<WelcomeHeader />);

  expect(screen.getByText("Good morning, Morgan lee!")).toBeInTheDocument();
  expect(screen.getByText("ML")).toBeInTheDocument();
  expect(screen.getByText("Here's your attendance overview for today.")).toBeInTheDocument();
});

test("falls back to the email name for employees without a display name", () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date(2026, 9, 14, 9, 30));
  state.user = { email: "avery@example.test" };
  render(<WelcomeHeader />);
  expect(screen.getByText("Good morning, Avery!")).toBeInTheDocument();
  expect(screen.getByText("A")).toBeInTheDocument();
});
