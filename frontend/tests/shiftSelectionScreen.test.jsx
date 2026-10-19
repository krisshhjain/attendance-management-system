import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, expect, test, vi } from "vitest";
import { API_BASE_URL } from "../src/lib/api.js";
import { ShiftSelectionScreen } from "../src/components/ShiftSelectionScreen.jsx";
import { server } from "./mocks/server.js";

const feedback = vi.hoisted(() => ({ success: vi.fn(), notifyError: vi.fn() }));
vi.mock("../src/feedback/useFeedback.js", () => ({
  FeedbackProvider: ({ children }) => children,
  useFeedback: () => feedback,
}));

const permanentShift = {
  id: 1,
  name: "Day Shift",
  code: "DAY",
  employment_type: "PERMANENT",
  start_time: "09:00",
  end_time: "17:00",
};

beforeEach(() => {
  vi.clearAllMocks();
  server.use(
    http.get(`${API_BASE_URL}/attendance/shifts/`, () =>
      HttpResponse.json({
        employment_type: "PERMANENT",
        requires_selection: true,
        shifts: [permanentShift],
      }),
    ),
  );
});

test("selects an eligible shift and submits its id before continuing", async () => {
  let assignment;
  server.use(
    http.post(`${API_BASE_URL}/attendance/my-shift/assign/`, async ({ request }) => {
      assignment = await request.json();
      return HttpResponse.json({ shift: permanentShift });
    }),
  );
  const onAssigned = vi.fn();
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const user = userEvent.setup();
  render(
    <QueryClientProvider client={queryClient}>
      <ShiftSelectionScreen onAssigned={onAssigned} />
    </QueryClientProvider>,
  );

  expect(await screen.findByText("Day Shift")).toBeInTheDocument();
  const confirm = screen.getByRole("button", { name: "Confirm Shift Selection" });
  expect(confirm).toBeDisabled();
  await user.click(screen.getByText("Day Shift"));
  expect(confirm).toBeEnabled();
  await user.click(confirm);

  await waitFor(() => expect(assignment).toEqual({ shift_id: 1 }));
  expect(onAssigned).toHaveBeenCalledWith(permanentShift);
  expect(feedback.success).toHaveBeenCalledWith("Shift assigned successfully.");
});

test("explains missing shift configuration and auto-assigned single shifts", async () => {
  server.use(
    http.get(`${API_BASE_URL}/attendance/shifts/`, () =>
      HttpResponse.json({ employment_type: "INTERN", shifts: [], requires_configuration: true }),
    ),
  );
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const { rerender } = render(
    <QueryClientProvider client={queryClient}>
      <ShiftSelectionScreen onAssigned={vi.fn()} />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("Shift Configuration Required")).toBeInTheDocument();
  expect(
    screen.getByText(/No shifts have been configured for INTERN employees/),
  ).toBeInTheDocument();

  queryClient.clear();
  server.use(
    http.get(`${API_BASE_URL}/attendance/shifts/`, () =>
      HttpResponse.json({ employment_type: "PERMANENT", shifts: [permanentShift] }),
    ),
  );
  const onAssigned = vi.fn();
  rerender(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ShiftSelectionScreen onAssigned={onAssigned} />
    </QueryClientProvider>,
  );
  expect(await screen.findByText("Shift Automatically Assigned")).toBeInTheDocument();
  await userEvent.setup().click(screen.getByRole("button", { name: "Continue to Dashboard" }));
  expect(onAssigned).toHaveBeenCalledWith(permanentShift);
});

test("reports failed shift assignment through shared feedback", async () => {
  server.use(
    http.post(`${API_BASE_URL}/attendance/my-shift/assign/`, () =>
      HttpResponse.json({ detail: "Assignment is no longer available." }, { status: 409 }),
    ),
  );
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const user = userEvent.setup();
  render(
    <QueryClientProvider client={queryClient}>
      <ShiftSelectionScreen onAssigned={vi.fn()} />
    </QueryClientProvider>,
  );
  await user.click(await screen.findByText("Day Shift"));
  await user.click(screen.getByRole("button", { name: "Confirm Shift Selection" }));
  await waitFor(() => expect(feedback.notifyError).toHaveBeenCalled());
  expect(feedback.notifyError).toHaveBeenCalledWith(
    expect.any(Error),
    expect.objectContaining({ title: "Shift assignment failed" }),
  );
});
