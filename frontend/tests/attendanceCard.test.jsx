import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { AttendanceCard } from "../src/components/AttendanceCard.jsx";
import { FeedbackProvider } from "../src/feedback/FeedbackProvider.jsx";

const attendanceState = vi.hoisted(() => ({
  getToday: vi.fn(),
  checkIn: vi.fn(),
  checkOut: vi.fn(),
  coordinates: vi.fn(),
}));
vi.mock("../src/lib/attendance.js", () => ({
  getToday: attendanceState.getToday,
  checkIn: attendanceState.checkIn,
  checkOut: attendanceState.checkOut,
}));

vi.mock("../src/lib/location.js", () => ({ getCurrentCoordinates: attendanceState.coordinates }));

function renderCard(onChanged = vi.fn()) {
  render(
    <FeedbackProvider>
      <AttendanceCard onChanged={onChanged} />
    </FeedbackProvider>,
  );
  return onChanged;
}

test("checks in with current coordinates, refreshes status, and informs the dashboard", async () => {
  attendanceState.getToday
    .mockResolvedValueOnce({ status: "NOT_CHECKED_IN", check_in: null, working_duration: 0 })
    .mockResolvedValue({
      status: "CHECKED_IN",
      check_in: new Date().toISOString(),
      working_duration: "00:00:00",
    });
  attendanceState.checkIn.mockResolvedValue(undefined);
  attendanceState.coordinates.mockResolvedValue({ latitude: 40.7, longitude: -74, accuracy: 8 });
  const onChanged = renderCard();
  const user = userEvent.setup();

  await user.click(await screen.findByRole("button", { name: "Check in" }));

  await waitFor(() =>
    expect(attendanceState.checkIn).toHaveBeenCalledWith({
      latitude: 40.7,
      longitude: -74,
      accuracy: 8,
    }),
  );
  expect(await screen.findByText("Checked In")).toBeInTheDocument();
  expect(
    screen.getByText(/5-minute safety period active before check-out unlocks/),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Check out \(/i })).toBeDisabled();
  expect(onChanged).toHaveBeenCalledOnce();
});

test("shows completed attendance without offering another attendance action", async () => {
  attendanceState.getToday.mockResolvedValue({
    status: "COMPLETED",
    check_in: "2026-10-14T09:00:00Z",
    check_out: "2026-10-14T17:00:00Z",
    working_duration: "08:00:00",
  });
  renderCard();

  expect(
    await screen.findByText("Your attendance for today is complete. Have a good evening."),
  ).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: /Check in|Check out/i })).not.toBeInTheDocument();
});
