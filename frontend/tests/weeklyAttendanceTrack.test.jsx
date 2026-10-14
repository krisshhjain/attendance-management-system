import { render, screen } from "@testing-library/react";
import { beforeEach, vi, test, expect } from "vitest";
import { WeeklyAttendanceTrack } from "../src/components/employee-dashboard/WeeklyAttendanceTrack.jsx";

const state = vi.hoisted(() => ({ queries: {}, holidays: null }));
vi.mock("@mui/icons-material", () => ({
  AccessTime: () => null,
  ChevronLeft: () => null,
  ChevronRight: () => null,
}));
vi.mock("@tanstack/react-query", () => ({
  useQuery: ({ queryKey }) => state.queries[queryKey[0]],
}));
vi.mock("../src/data/holidayCalendar.js", () => ({ useActiveHolidays: () => state.holidays }));

function renderTrack(todayData) {
  return render(<WeeklyAttendanceTrack todayData={todayData} />);
}

beforeEach(() => {
  state.queries = {
    attendanceHistory: { data: [], isLoading: false },
    myShift: { data: { shift: null }, isLoading: false },
  };
  state.holidays = { data: [], isLoading: false, isError: false };
});

function localDateKey(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

test("summarizes weekly attendance and overlays today's live attendance", () => {
  const today = new Date();
  const todayKey = localDateKey(today);
  state.queries.attendanceHistory.data = [
    {
      date: todayKey,
      status: "INCOMPLETE",
      check_in: `${todayKey}T09:00:00`,
      working_duration: "01:00:00",
    },
  ];
  state.queries.myShift.data = {
    shift: { name: "Day shift", start_time: "09:00", end_time: "17:00" },
  };

  renderTrack({ status: "CHECKED_IN", active_check_in: `${todayKey}T09:00:00` });

  expect(screen.getByText("Weekly attendance")).toBeInTheDocument();
  expect(screen.getByText("Day shift · 09:00 – 17:00")).toBeInTheDocument();
  expect(screen.getAllByText("In progress").length).toBeGreaterThan(0);
  expect(screen.getByText("This week")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Previous week" })).toBeEnabled();
});

test("explains when no shift is assigned", () => {
  renderTrack();

  expect(
    screen.getByText("Assign a shift to see attendance against scheduled hours."),
  ).toBeInTheDocument();
});

test("hides attendance statuses when holiday verification fails", () => {
  state.queries.myShift.data = {
    shift: { name: "Day shift", start_time: "09:00", end_time: "17:00" },
  };
  state.holidays.isError = true;

  renderTrack();

  expect(
    screen.getByText(
      "Holiday data could not be loaded. Attendance statuses are hidden until it is available.",
    ),
  ).toBeInTheDocument();
});

test("formats duration variants across an overnight shift and labels holiday and leave days", () => {
  const today = new Date();
  const monday = new Date(today);
  monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));
  const key = (offset) => {
    const date = new Date(monday);
    date.setDate(monday.getDate() + offset);
    return localDateKey(date);
  };
  state.queries.attendanceHistory.data = [
    { date: key(0), status: "PRESENT", working_duration: 1800 },
    { date: key(1), status: "LEAVE", working_duration: "1 days, 01:30:00" },
    { date: key(2), status: "COMPLETED", working_duration: "90" },
    { date: key(3), status: "UNRECOGNIZED", working_duration: "not-a-duration" },
    { date: key(5), status: "PRESENT", working_duration: "3:45" },
    {
      date: key(4),
      status: "HOLIDAY",
      holiday_name: "Founders Day",
      check_in: "not-a-timestamp",
      check_out: null,
      working_duration: "not-a-duration",
    },
  ];
  state.queries.myShift.data = {
    shift: { name: "Overnight", start_time: "22:00", end_time: "06:00" },
  };
  renderTrack();

  expect(screen.getByText("Overnight · 22:00 – 06:00")).toBeInTheDocument();
  expect(screen.getAllByText("Leave").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Holiday").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Weekend").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Present").length).toBeGreaterThan(0);
  expect(screen.getAllByText("Not recorded").length).toBeGreaterThan(0);
  expect(screen.getByText("3h 45m")).toBeInTheDocument();
}, 15_000);
