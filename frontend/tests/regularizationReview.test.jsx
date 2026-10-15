import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { Route } from "../src/routes/administration.regularization.$id.jsx";

const state = vi.hoisted(() => ({
  id: "77",
  request: vi.fn(),
  approve: vi.fn(),
  reject: vi.fn(),
  navigate: vi.fn(),
  success: vi.fn(),
  notifyError: vi.fn(),
}));
vi.mock("@tanstack/react-router", () => ({
  createFileRoute: () => (options) => ({ ...options, useParams: () => ({ id: state.id }) }),
  useNavigate: () => state.navigate,
}));
vi.mock("../src/components/RequireAuth.jsx", () => ({ RequireAuth: ({ children }) => children }));
vi.mock("../src/lib/api.js", () => ({
  fetchAdminRegularizationRequest: state.request,
  approveRegularizationRequest: state.approve,
  rejectRegularizationRequest: state.reject,
}));
vi.mock("../src/feedback/useFeedback.js", () => ({
  useFeedback: () => ({ success: state.success, notifyError: state.notifyError }),
}));

function renderPage() {
  const Component = Route.component;
  return render(<Component />);
}

beforeEach(() => {
  vi.clearAllMocks();
  state.request.mockResolvedValue({
    id: 77,
    status: "PENDING",
    employee_name: "Avery Lee",
    employee_email: "avery@example.test",
    request_type: "DATE_RANGE",
    period_start: "2026-10-12",
    period_end: "2026-10-13",
    can_be_processed: true,
    reason: "Missed both clock events",
    days: [
      { id: 1, attendance_date: "2026-10-12", requested_check_in: null, requested_check_out: null },
      { id: 2, attendance_date: "2026-10-13", requested_check_in: null, requested_check_out: null },
    ],
  });
  state.approve.mockResolvedValue({ status: "APPROVED" });
  state.reject.mockResolvedValue({ status: "REJECTED" });
});

test("requires a final time for each requested day and submits the complete correction", async () => {
  const user = userEvent.setup();
  renderPage();

  expect(await screen.findByText("Avery Lee")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Approve" }));
  expect(
    await screen.findByText("Enter at least one final time for every requested date."),
  ).toBeInTheDocument();
  expect(state.approve).not.toHaveBeenCalled();

  const checkIns = screen.getAllByLabelText("Final check-in");
  const checkOuts = screen.getAllByLabelText("Final check-out");
  await user.type(checkIns[0], "09:00");
  await user.type(checkOuts[0], "17:00");
  await user.type(checkIns[1], "09:30");
  await user.type(checkOuts[1], "17:30");
  await user.click(screen.getByRole("button", { name: "Approve" }));

  await waitFor(() =>
    expect(state.approve).toHaveBeenCalledWith("77", {
      days: [
        { id: 1, check_in: "2026-10-12T09:00:00", check_out: "2026-10-12T17:00:00" },
        { id: 2, check_in: "2026-10-13T09:30:00", check_out: "2026-10-13T17:30:00" },
      ],
    }),
  );
  expect(state.success).toHaveBeenCalledWith("Regularization approved successfully.");
}, 15_000);

test("rejects invalid day time order and requires a reason to reject", async () => {
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("Avery Lee");

  const checkIns = screen.getAllByLabelText("Final check-in");
  const checkOuts = screen.getAllByLabelText("Final check-out");
  await user.type(checkIns[0], "17:00");
  await user.type(checkOuts[0], "09:00");
  await user.type(checkIns[1], "09:00");
  await user.click(screen.getByRole("button", { name: "Approve" }));
  expect(
    await screen.findByText("Each check-out must be later than its check-in."),
  ).toBeInTheDocument();

  expect(screen.getByRole("button", { name: "Reject" })).toBeDisabled();
  expect(state.reject).not.toHaveBeenCalled();
  await user.type(
    screen.getByRole("textbox", { name: "Rejection reason (required to reject)" }),
    "No supporting information",
  );
  await user.click(screen.getByRole("button", { name: "Reject" }));
  await waitFor(() => expect(state.reject).toHaveBeenCalledWith("77", "No supporting information"));
  expect(state.success).toHaveBeenCalledWith("Regularization rejected.");
}, 15_000);

test("shows a recoverable not-found response and returns to the review queue", async () => {
  state.request.mockRejectedValue(new Error("Request no longer exists."));
  const user = userEvent.setup();
  renderPage();

  expect(await screen.findByText("Request no longer exists.")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Back to Regularization" }));
  expect(state.navigate).toHaveBeenCalledWith({ to: "/admin-regularization" });
});

test("approves a single-day correction with one final time and reports server rejection", async () => {
  state.request.mockResolvedValue({
    id: 77,
    status: "PENDING",
    employee_name: "Avery Lee",
    attendance_date: "2026-10-12",
    requested_check_in: "not-a-date",
    requested_check_out: null,
    can_be_processed: true,
    days: [],
  });
  state.approve.mockRejectedValue(new Error("The record was updated by another reviewer."));
  const user = userEvent.setup();
  renderPage();

  expect(await screen.findByText("Avery Lee")).toBeInTheDocument();
  expect(screen.getByLabelText("Final check-in")).toHaveValue("");
  expect(screen.getAllByText("Not recorded").length).toBeGreaterThan(0);
  await user.type(screen.getByLabelText("Final check-in"), "09:15");
  await user.click(screen.getByRole("button", { name: "Approve" }));

  await waitFor(() =>
    expect(state.approve).toHaveBeenCalledWith("77", {
      check_in: "2026-10-12T09:15:00",
      check_out: null,
    }),
  );
  expect(state.notifyError).toHaveBeenCalledWith(
    expect.objectContaining({ message: "The record was updated by another reviewer." }),
    expect.objectContaining({ title: "Regularization approval failed" }),
  );
}, 15_000);
