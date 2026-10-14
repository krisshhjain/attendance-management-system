import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { test, expect, vi } from "vitest";
import { Route } from "../src/routes/regularization.jsx";
import { FeedbackProvider } from "../src/feedback/FeedbackProvider.jsx";
import { API_BASE_URL } from "../src/lib/api.js";
import { server } from "./mocks/server.js";

vi.mock("../src/components/RequireAuth.jsx", () => ({
  RequireAuth: ({ children }) => children,
}));

const requestQuota = {
  weekly_used: 0,
  weekly_limit: 3,
  weekly_remaining: 3,
  monthly_used: 0,
  monthly_limit: 10,
  monthly_remaining: 10,
  week_start: "2026-10-12",
  week_end: "2026-10-18",
  month: "2026-10",
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Page = Route.options.component;
  return render(
    <QueryClientProvider client={queryClient}>
      <FeedbackProvider>
        <Page />
      </FeedbackProvider>
    </QueryClientProvider>,
  );
}

test("validates and submits a correction with a normalized time and the selected date", async () => {
  const RealDate = Date;
  const fixedTimestamp = new RealDate(2026, 9, 14, 12).getTime();
  class FixedDate extends RealDate {
    constructor(...args) {
      super(...(args.length ? args : [fixedTimestamp]));
    }

    static now() {
      return fixedTimestamp;
    }
  }
  vi.stubGlobal("Date", FixedDate);

  let requests = [];
  let payload;
  server.use(
    http.get(`${API_BASE_URL}/attendance/regularization/list/`, () => HttpResponse.json(requests)),
    http.get(`${API_BASE_URL}/attendance/history/`, () => HttpResponse.json([])),
    http.get(`${API_BASE_URL}/attendance/regularization/quota/`, () =>
      HttpResponse.json(requestQuota),
    ),
    http.get(`${API_BASE_URL}/holidays/`, () => HttpResponse.json([])),
    http.post(`${API_BASE_URL}/attendance/regularization/`, async ({ request }) => {
      payload = await request.json();
      requests = [
        {
          id: 1,
          attendance_date: "2026-10-14",
          period_type: "DAY",
          request_type: "INCORRECT_ATTENDANCE",
          status: "PENDING",
          reason: "Forgot to check in",
        },
      ];
      return HttpResponse.json({ id: 1 }, { status: 201 });
    }),
  );
  const user = userEvent.setup();

  renderPage();

  expect(
    await screen.findByText("You have not submitted any regularization requests."),
  ).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Request correction" }));

  await user.click(screen.getByRole("button", { name: "Submit request" }));
  expect(
    screen.getByText("Choose at least one attendance date and enter a correction."),
  ).toBeInTheDocument();

  await user.type(screen.getByLabelText("Corrected check-in"), "9:30 AM");
  await user.click(screen.getByRole("button", { name: "Submit request" }));
  expect(screen.getByText(/add a reason/)).toBeInTheDocument();

  await user.type(screen.getByLabelText("Reason"), "  Forgot to check in  ");
  await user.click(screen.getByRole("button", { name: "Submit request" }));

  await waitFor(() =>
    expect(payload).toEqual({
      period_type: "DAY",
      days: [
        {
          attendance_date: "2026-10-14",
          request_type: "INCORRECT_ATTENDANCE",
          requested_check_in: "2026-10-14T09:30:00",
          requested_check_out: null,
          reason: "Forgot to check in",
          description: "",
        },
      ],
      attachment: "",
    }),
  );
  expect(await screen.findByText("Regularization request submitted.")).toBeInTheDocument();
  expect(screen.getAllByText("PENDING").length).toBeGreaterThan(0);
});

test("blocks requests for registered holidays and disables submission when quota is exhausted", async () => {
  const RealDate = Date;
  const fixedTimestamp = new RealDate(2026, 9, 14, 12).getTime();
  class FixedDate extends RealDate {
    constructor(...args) {
      super(...(args.length ? args : [fixedTimestamp]));
    }

    static now() {
      return fixedTimestamp;
    }
  }
  vi.stubGlobal("Date", FixedDate);
  server.use(
    http.get(`${API_BASE_URL}/attendance/regularization/list/`, () => HttpResponse.json([])),
    http.get(`${API_BASE_URL}/attendance/history/`, () => HttpResponse.json([])),
    http.get(`${API_BASE_URL}/attendance/regularization/quota/`, () =>
      HttpResponse.json({ ...requestQuota, weekly_used: 3, weekly_remaining: 0 }),
    ),
    http.get(`${API_BASE_URL}/holidays/`, () =>
      HttpResponse.json([{ date: "2026-10-14", name: "Company Day", is_active: true }]),
    ),
  );
  const user = userEvent.setup();

  renderPage();
  await screen.findByText("You have not submitted any regularization requests.");
  await user.click(screen.getByRole("button", { name: "Request correction" }));

  expect(screen.getByText("Holiday: Company Day")).toBeInTheDocument();
  expect(
    screen.getByText("You have reached this week’s allowance of 3 requests."),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Submit request" })).toBeDisabled();
});
