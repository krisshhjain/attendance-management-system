import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { TodayAttendanceWidget } from "../src/components/employee-dashboard/TodayAttendanceWidget.jsx";

const state = vi.hoisted(() => ({
  feedback: { success: vi.fn(), notifyError: vi.fn() },
  shift: null,
  checkIn: vi.fn(),
  checkOut: vi.fn(),
  coordinates: vi.fn(),
  officeLocations: vi.fn(),
  navigate: vi.fn(),
}));

vi.mock("@tanstack/react-router", () => ({ useNavigate: () => state.navigate }));
vi.mock("@tanstack/react-query", () => ({ useQuery: () => ({ data: state.shift }) }));
vi.mock("../src/feedback/useFeedback.js", () => ({ useFeedback: () => state.feedback }));
vi.mock("../src/lib/attendance.js", () => ({ checkIn: state.checkIn, checkOut: state.checkOut }));
vi.mock("../src/lib/location.js", () => ({ getCurrentCoordinates: state.coordinates }));
vi.mock("../src/lib/api.js", () => ({
  fetchMyShift: vi.fn(),
  fetchOfficeLocations: (...args) => state.officeLocations(...args),
}));
vi.mock("../src/components/employee-dashboard/FaceVerificationModal.jsx", () => ({
  FaceVerificationModal: ({ open, actionType, locationData }) =>
    open ? (
      <div role="dialog">
        Verify {actionType} at {locationData.latitude}, {locationData.longitude}
      </div>
    ) : null,
}));
vi.mock("@mui/icons-material/CameraAltOutlined", () => ({ default: () => null }));
vi.mock("@mui/icons-material/ScheduleOutlined", () => ({ default: () => null }));

function renderWidget(props = {}) {
  return render(
    <TodayAttendanceWidget
      data={{ status: "NOT_CHECKED_IN", working_duration: 0, ...props.data }}
      loading={false}
      loadError={false}
      reloadData={vi.fn().mockResolvedValue(undefined)}
      {...props}
    />,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  state.shift = null;
  state.coordinates.mockResolvedValue({ latitude: 40.7, longitude: -74, accuracy: 10 });
  state.officeLocations.mockResolvedValue([]);
  state.checkIn.mockResolvedValue(undefined);
  state.checkOut.mockResolvedValue(undefined);
});

test("marks attendance with current coordinates and refreshes the dashboard", async () => {
  const reloadData = vi.fn().mockResolvedValue(undefined);
  const user = userEvent.setup();
  renderWidget({ reloadData });

  await user.click(screen.getByRole("button", { name: "Check In" }));

  expect(state.checkIn).toHaveBeenCalledWith({ latitude: 40.7, longitude: -74, accuracy: 10 });
  expect(state.feedback.success).toHaveBeenCalledWith("Attendance marked successfully.");
  expect(reloadData).toHaveBeenCalledOnce();
});

test("reports a location failure and always returns to the ready state", async () => {
  state.coordinates.mockRejectedValue(new Error("Location permission denied"));
  const user = userEvent.setup();
  renderWidget();

  await user.click(screen.getByRole("button", { name: "Check In" }));

  expect(state.checkIn).not.toHaveBeenCalled();
  expect(state.feedback.notifyError).toHaveBeenCalledWith(
    expect.objectContaining({ message: "Location permission denied" }),
    expect.objectContaining({ title: "Attendance unavailable" }),
  );
  expect(screen.getByRole("button", { name: "Check In" })).toBeEnabled();
});

test("renders shift and incomplete attendance guidance and navigates to regularization", async () => {
  state.shift = { shift: { name: "Day", start_time: "09:00", end_time: "17:00" } };
  const user = userEvent.setup();
  renderWidget({
    data: {
      status: "CHECKED_IN",
      active_check_in: new Date().toISOString(),
      previous_incomplete_attendance: { date: "2026-10-13" },
    },
  });

  expect(screen.getByText("Day")).toBeInTheDocument();
  expect(screen.getByText("09:00 - 17:00")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Regularize" }));
  expect(state.navigate).toHaveBeenCalledWith({ to: "/regularization" });
  expect(screen.getByRole("button", { name: "Check Out" })).toBeEnabled();
});

test("shows loading and retry states", async () => {
  const reloadData = vi.fn();
  const { rerender } = renderWidget({ loading: true, reloadData });
  expect(screen.getByRole("progressbar")).toBeInTheDocument();

  rerender(<TodayAttendanceWidget data={null} loading={false} loadError reloadData={reloadData} />);
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "Retry" }));
  expect(reloadData).toHaveBeenCalledOnce();
});

test("shows holiday context and safely formats incomplete or malformed attendance values", () => {
  renderWidget({
    data: {
      status: "HOLIDAY",
      holiday_name: "Founders Day",
      check_in: "not-a-timestamp",
      check_out: null,
      working_duration: "3661",
    },
  });

  expect(screen.getAllByText("Holiday")).toHaveLength(2);
  expect(screen.getByText("Founders Day")).toBeInTheDocument();
  expect(screen.getByText("01h 01m")).toBeInTheDocument();
  expect(screen.getAllByText("--:--")).toHaveLength(2);
  expect(screen.getByRole("button", { name: "Check In" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Check Out" })).toBeDisabled();
});

test("opens face verification only after confirming a precise office location", async () => {
  state.coordinates.mockResolvedValue({ latitude: 10, longitude: 20, accuracy: 25 });
  state.officeLocations.mockResolvedValue([
    { latitude: 10, longitude: 20, radius_meters: 150, is_active: true },
  ]);
  const user = userEvent.setup();
  renderWidget();

  await user.click(screen.getByRole("button", { name: "Face Check In" }));

  expect(await screen.findByRole("dialog")).toHaveTextContent("Verify in at 10, 20");
  expect(state.officeLocations).toHaveBeenCalledOnce();
});

test("blocks face verification when GPS accuracy is outside the supported range", async () => {
  state.coordinates.mockResolvedValue({ latitude: 10, longitude: 20, accuracy: 500 });
  const user = userEvent.setup();
  renderWidget();

  await user.click(screen.getByRole("button", { name: "Face Check In" }));

  expect(state.officeLocations).not.toHaveBeenCalled();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(state.feedback.notifyError).toHaveBeenCalledWith(
    expect.objectContaining({
      message: "Your location accuracy is too low. Please enable precise location and try again.",
    }),
    expect.objectContaining({ title: "Location unavailable" }),
  );
});
