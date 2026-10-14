import { render, screen, within } from "@testing-library/react";
import { expect, test, vi } from "vitest";
import { AttendanceChart } from "../src/components/dashboard/AttendanceChart.jsx";

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }) => <div>{children}</div>,
  PieChart: ({ children }) => <div>{children}</div>,
  Pie: ({ data }) => (
    <ul aria-label="Attendance segments">
      {data.map(({ name, value }) => (
        <li key={name}>{`${name}: ${value}`}</li>
      ))}
    </ul>
  ),
  Cell: () => null,
  Tooltip: () => null,
  Legend: () => null,
}));

test("shows working-day attendance totals without allowing a negative not-arrived count", () => {
  render(
    <AttendanceChart data={{ active_employees: 4, checked_in_today: 3, completed_today: 2 }} />,
  );
  expect(screen.getByText("Today's attendance status")).toBeInTheDocument();
  const chart = screen.getByRole("list", { name: "Attendance segments" });
  expect(within(chart).getByText("Completed: 2")).toBeInTheDocument();
  expect(within(chart).getByText("Currently In: 3")).toBeInTheDocument();
  expect(within(chart).getByText("Not Arrived: 0")).toBeInTheDocument();
});

test.each([
  [{ is_working_day: false, day_type: "WEEKEND", active_employees: 8 }, "Weekend: 8", "Weekend"],
  [
    {
      is_working_day: false,
      day_type: "HOLIDAY",
      holiday_name: "Founders Day",
      active_employees: 8,
    },
    "Holiday: 8",
    /Founders Day/,
  ],
  [
    { is_working_day: false, day_type: "OTHER", active_employees: 8 },
    "Non-working day: 8",
    "Today's attendance status",
  ],
])("labels off-day attendance using the configured day type", (data, segment, subtitle) => {
  const { container } = render(<AttendanceChart data={data} />);
  expect(screen.getByText(subtitle)).toBeInTheDocument();
  expect(within(container).getByText(segment)).toBeInTheDocument();
});
