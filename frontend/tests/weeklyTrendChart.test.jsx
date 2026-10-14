import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { expect, test, vi } from "vitest";
import { API_BASE_URL } from "../src/lib/api.js";
import { WeeklyTrendChart } from "../src/components/dashboard/WeeklyTrendChart.jsx";
import { server } from "./mocks/server.js";

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }) => <div>{children}</div>,
  AreaChart: ({ data }) => (
    <div data-testid="attendance-trend">
      {data.map((day) => (
        <div key={day.dateStr} data-testid="trend-day">
          <span>{day.dateStr}</span>
          <span>{day.Present} present</span>
          <span>{day["On Leave"]} on leave</span>
        </div>
      ))}
    </div>
  ),
  Area: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
}));

test("requests only weekdays and summarizes present, incomplete, and leave records", async () => {
  const queriedDates = [];
  server.use(
    http.get(`${API_BASE_URL}/admin/attendance/`, ({ request }) => {
      queriedDates.push(new URL(request.url).searchParams.get("date"));
      return HttpResponse.json({
        results: [
          { status: "PRESENT" },
          { status: "INCOMPLETE" },
          { status: "LEAVE" },
          { status: "ABSENT" },
        ],
      });
    }),
  );
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <WeeklyTrendChart />
    </QueryClientProvider>,
  );

  expect(await screen.findByTestId("attendance-trend")).toBeInTheDocument();
  const weekdays = [];
  const day = new Date();
  for (let index = 0; index < 7; index += 1) {
    if (day.getDay() !== 0 && day.getDay() !== 6) weekdays.push(day.toLocaleDateString("en-CA"));
    day.setDate(day.getDate() - 1);
  }
  await waitFor(() => expect(queriedDates).toHaveLength(weekdays.length));
  expect([...queriedDates].sort()).toEqual([...weekdays].sort());
  expect(screen.getAllByTestId("trend-day")).toHaveLength(weekdays.length);
  for (const row of screen.getAllByTestId("trend-day")) {
    expect(within(row).getByText("2 present")).toBeInTheDocument();
    expect(within(row).getByText("1 on leave")).toBeInTheDocument();
  }
});
