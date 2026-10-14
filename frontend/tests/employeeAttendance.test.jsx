import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, vi, test, expect } from "vitest";
import { EmployeeAttendancePage } from "../src/components/employee-dashboard/EmployeeAttendancePage.jsx";

const state = vi.hoisted(() => ({ query: null, holidays: null }));
vi.mock("@mui/icons-material", () => ({
  CalendarMonthOutlined: () => null,
  ChevronLeft: () => null,
  ChevronRight: () => null,
  ViewListOutlined: () => null,
  ViewWeekOutlined: () => null,
}));
vi.mock("@tanstack/react-query", () => ({ useQuery: () => state.query }));
vi.mock("../src/data/holidayCalendar.js", () => ({
  useActiveHolidays: () => state.holidays,
  indexActiveHolidays: (holidays) => new Map(holidays.map((holiday) => [holiday.date, holiday])),
}));

function renderPage() {
  return render(<EmployeeAttendancePage />);
}

beforeEach(() => {
  state.query = { data: [], isLoading: false, isError: false, refetch: vi.fn() };
  state.holidays = { data: [], isError: false };
});

function dateKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

test("shows monthly attendance, navigates months, and switches to the list view", async () => {
  const today = new Date();
  const todayKey = dateKey(today);
  state.query.data = [
    {
      date: todayKey,
      status: "PRESENT",
      check_in: `${todayKey}T09:00:00`,
      check_out: `${todayKey}T17:00:00`,
      working_duration: "08:00:00",
    },
  ];
  const user = userEvent.setup();

  renderPage();

  expect(screen.getByText("My Attendance")).toBeInTheDocument();
  expect(screen.getByText("1 days")).toBeInTheDocument();
  const monthLabel = new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric" }).format(
    today,
  );
  expect(screen.getByText(monthLabel)).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Previous month" }));
  const previousMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);
  const previousLabel = new Intl.DateTimeFormat("en-US", {
    month: "long",
    year: "numeric",
  }).format(previousMonth);
  expect(screen.getByText(previousLabel)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Today" }));
  expect(screen.getByText(monthLabel)).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "List" }));
  const row = screen.getByRole("row", { name: /Present/ });
  expect(within(row).getByText("Present")).toBeInTheDocument();
  expect(within(row).getByText("8h 0m")).toBeInTheDocument();
});

test("shows a recovery action after an attendance history failure", () => {
  state.query.isError = true;
  const refetch = vi.fn();
  state.query.refetch = refetch;
  renderPage();

  expect(screen.getByText("Could not load attendance.")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  expect(refetch).not.toHaveBeenCalled();
});

test("keeps holiday labels over stale absences in calendar views but preserves history in the list", async () => {
  const today = new Date();
  const holiday = Array.from(
    { length: 7 },
    (_, index) => new Date(today.getFullYear(), today.getMonth(), index + 1),
  ).find((date) => date.getDay() !== 0 && date.getDay() !== 6);
  const holidayKey = dateKey(holiday);
  state.query.data = [
    {
      date: holidayKey,
      status: "ABSENT",
      check_in: null,
      check_out: null,
      working_duration: 0,
    },
  ];
  state.holidays.data = [{ date: holidayKey, name: "Founders Day" }];
  const user = userEvent.setup();
  renderPage();

  expect(screen.getByText("Founders Day")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Week" }));
  expect(screen.getByText("Founders Day")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "List" }));
  expect(screen.getByRole("row", { name: /Absent/ })).toBeInTheDocument();
});

test("renders attendance statuses and narrows the list to leave records", async () => {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth();
  const weekdays = Array.from(
    { length: new Date(year, month + 1, 0).getDate() },
    (_, index) => index + 1,
  )
    .filter((day) => ![0, 6].includes(new Date(year, month, day).getDay()))
    .slice(0, 6);
  const [presentDay, incompleteDay, leaveDay, absentDay, holidayDay, customDay] = weekdays;
  const key = (day) =>
    `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  state.query.data = [
    { date: key(presentDay), status: "PRESENT", working_duration: "08:05:00" },
    {
      date: key(incompleteDay),
      status: "INCOMPLETE",
      check_in: `${key(incompleteDay)}T09:00:00`,
      check_out: null,
    },
    { date: key(leaveDay), status: "LEAVE", working_duration: 0 },
    { date: key(absentDay), status: "ABSENT", working_duration: 0 },
    { date: key(holidayDay), status: "HOLIDAY", holiday_name: "Founders Day", working_duration: 0 },
    { date: key(customDay), status: "CUSTOM_STATUS", working_duration: 0 },
  ];
  state.holidays.data = [{ date: key(holidayDay), name: "Founders Day" }];
  const user = userEvent.setup();
  renderPage();

  expect(screen.getAllByText("Present").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Checked In").length).toBeGreaterThan(0);
  expect(screen.getAllByText("On Leave").length).toBeGreaterThan(0);
  expect(screen.getByText("Founders Day")).toBeInTheDocument();
  expect(screen.getByText("CUSTOM_STATUS")).toBeInTheDocument();
  expect(screen.getAllByText("Weekend").length).toBeGreaterThan(0);

  await user.click(screen.getByRole("button", { name: "List" }));
  await user.click(screen.getByRole("combobox"));
  await user.click(screen.getByRole("option", { name: "On Leave" }));
  expect(screen.getByRole("row", { name: /On Leave/ })).toBeInTheDocument();
  expect(screen.queryByRole("row", { name: /Present/ })).not.toBeInTheDocument();
}, 15_000);
