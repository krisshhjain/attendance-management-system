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
