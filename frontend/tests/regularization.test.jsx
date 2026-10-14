import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
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
}, 15_000);

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

test("rejects malformed times and a checkout earlier than the corrected check-in", async () => {
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
      HttpResponse.json(requestQuota),
    ),
    http.get(`${API_BASE_URL}/holidays/`, () => HttpResponse.json([])),
  );
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("You have not submitted any regularization requests.");
  await user.click(screen.getByRole("button", { name: "Request correction" }));

  await user.type(screen.getByLabelText("Corrected check-in"), "25:70");
  await user.type(screen.getByLabelText("Reason"), "Correcting the workday");
  await user.click(screen.getByRole("button", { name: "Submit request" }));
  expect(screen.getByText(/enter a valid time/)).toBeInTheDocument();

  const checkIn = screen.getByLabelText("Corrected check-in");
  await user.clear(checkIn);
  await user.type(checkIn, "9:00");
  await user.type(screen.getByLabelText("Corrected check-out"), "8:00");
  await user.click(screen.getByRole("button", { name: "Submit request" }));
  expect(screen.getByText(/check-out must be later than check-in/)).toBeInTheDocument();
}, 15_000);

test("submits one correction covering multiple eligible dates in the selected week", async () => {
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
  let payload;
  server.use(
    http.get(`${API_BASE_URL}/attendance/regularization/list/`, () => HttpResponse.json([])),
    http.get(`${API_BASE_URL}/attendance/history/`, () => HttpResponse.json([])),
    http.get(`${API_BASE_URL}/attendance/regularization/quota/`, () =>
      HttpResponse.json(requestQuota),
    ),
    http.get(`${API_BASE_URL}/holidays/`, () => HttpResponse.json([])),
    http.post(`${API_BASE_URL}/attendance/regularization/`, async ({ request }) => {
      payload = await request.json();
      return HttpResponse.json({ id: 5 }, { status: 201 });
    }),
  );
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("You have not submitted any regularization requests.");
  await user.click(screen.getByRole("button", { name: "Request correction" }));
  await user.click(screen.getByRole("combobox", { name: "Period" }));
  await user.click(screen.getByRole("option", { name: "Week" }));
  expect(screen.getByRole("combobox", { name: "Week" })).toHaveTextContent(/Oct 12.*Oct 18, 2026/);
  await user.click(screen.getByRole("combobox", { name: "Week" }));
  await user.click(screen.getByRole("option", { name: /Oct 12.*Oct 18, 2026/ }));

  const eligibleDates = [...document.querySelectorAll("[data-attendance-date]")].slice(0, 2);
  expect(eligibleDates).toHaveLength(2);
  for (const [index, card] of eligibleDates.entries()) {
    await user.type(within(card).getByLabelText("Corrected check-in"), index ? "9:15" : "9:00");
    await user.type(within(card).getByLabelText("Reason"), `Workday correction ${index + 1}`);
  }
  await user.click(screen.getByRole("button", { name: "Submit request" }));

  await waitFor(() => expect(payload?.period_type).toBe("WEEK"));
  expect(payload.days).toHaveLength(2);
  expect(payload.days.map((day) => day.attendance_date)).toEqual(
    eligibleDates.map((card) => card.getAttribute("data-attendance-date")),
  );
  expect(await screen.findByText("Regularization request submitted.")).toBeInTheDocument();
}, 30_000);

test("reports an unavailable regularization request list instead of showing a false empty state", async () => {
  let attempts = 0;
  server.use(
    http.get(`${API_BASE_URL}/attendance/regularization/list/`, () => {
      attempts += 1;
      if (attempts === 1)
        return HttpResponse.json({ detail: "Service unavailable" }, { status: 503 });
      return HttpResponse.json([
        {
          id: 41,
          attendance_date: "2026-10-14",
          period_type: "DAY",
          status: "APPROVED",
          requested_check_in: "not-a-date",
          reason: "Clock verified by supervisor",
          reviewed_by_name: "Morgan Manager",
        },
      ]);
    }),
    http.get(`${API_BASE_URL}/attendance/history/`, () => HttpResponse.json([])),
    http.get(`${API_BASE_URL}/attendance/regularization/quota/`, () =>
      HttpResponse.json(requestQuota),
    ),
    http.get(`${API_BASE_URL}/holidays/`, () => HttpResponse.json([])),
  );
  renderPage();

  expect(await screen.findByText("Service unavailable")).toBeInTheDocument();
  expect(
    screen.queryByText("You have not submitted any regularization requests."),
  ).not.toBeInTheDocument();
  expect(attempts).toBe(1);
});

test("submits a month-scoped correction for an eligible workday", async () => {
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
  let payload;
  server.use(
    http.get(`${API_BASE_URL}/attendance/regularization/list/`, () => HttpResponse.json([])),
    http.get(`${API_BASE_URL}/attendance/history/`, () => HttpResponse.json([])),
    http.get(`${API_BASE_URL}/attendance/regularization/quota/`, () =>
      HttpResponse.json(requestQuota),
    ),
    http.get(`${API_BASE_URL}/holidays/`, () => HttpResponse.json([])),
    http.post(`${API_BASE_URL}/attendance/regularization/`, async ({ request }) => {
      payload = await request.json();
      return HttpResponse.json({ id: 52 }, { status: 201 });
    }),
  );
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("You have not submitted any regularization requests.");
  await user.click(screen.getByRole("button", { name: "Request correction" }));
  await user.click(screen.getByRole("combobox", { name: "Period" }));
  await user.click(screen.getByRole("option", { name: "Month" }));
  expect(screen.getByRole("combobox", { name: "Month" })).toHaveTextContent("October 2026");

  const targetDay = document.querySelector('[data-attendance-date="2026-10-12"]');
  expect(targetDay).not.toBeNull();
  await user.type(within(targetDay).getByLabelText("Corrected check-in"), "9:15 PM");
  await user.type(within(targetDay).getByLabelText("Reason"), "Month period correction");
  await user.click(screen.getByRole("button", { name: "Submit request" }));

  await waitFor(() => expect(payload?.period_type).toBe("MONTH"));
  expect(payload.days).toEqual([
    expect.objectContaining({
      attendance_date: "2026-10-12",
      requested_check_in: "2026-10-12T21:15:00",
      reason: "Month period correction",
    }),
  ]);
}, 30_000);

test("blocks submission if holiday eligibility could not be verified", async () => {
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
      HttpResponse.json(requestQuota),
    ),
    http.get(`${API_BASE_URL}/holidays/`, () =>
      HttpResponse.json({ detail: "Holiday service unavailable." }, { status: 503 }),
    ),
  );
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("You have not submitted any regularization requests.");
  await user.click(screen.getByRole("button", { name: "Request correction" }));
  expect(await screen.findByText(/Company holiday dates could not be loaded/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Submit request" })).toBeDisabled();
});

test("rejects an oversized supporting file before submitting a correction", async () => {
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
      HttpResponse.json(requestQuota),
    ),
    http.get(`${API_BASE_URL}/holidays/`, () => HttpResponse.json([])),
  );
  const user = userEvent.setup({ applyAccept: false });
  renderPage();
  await screen.findByText("You have not submitted any regularization requests.");
  await user.click(screen.getByRole("button", { name: "Request correction" }));
  const oversizedDocument = new File([new Uint8Array(5 * 1024 * 1024 + 1)], "evidence.pdf", {
    type: "application/pdf",
  });
  await user.upload(screen.getByLabelText("Attach supporting document"), oversizedDocument);
  expect(await screen.findByText("Attachment must be 5 MB or smaller.")).toBeInTheDocument();
  expect(screen.queryByText("Selected: evidence.pdf")).not.toBeInTheDocument();
});
