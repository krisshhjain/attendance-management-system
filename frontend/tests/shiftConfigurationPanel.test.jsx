import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { API_BASE_URL } from "../src/lib/api.js";
import { ShiftConfigurationPanel } from "../src/components/ShiftConfigurationPanel.jsx";
import { server } from "./mocks/server.js";

const feedback = vi.hoisted(() => ({ success: vi.fn(), notifyError: vi.fn() }));
vi.mock("../src/feedback/useFeedback.js", () => ({ useFeedback: () => feedback }));

const configuration = {
  PERMANENT: [{ id: 1, name: "Day Shift", code: "DAY", start_time: "09:00", end_time: "17:00" }],
  CONTRACT: [],
  INTERN: [],
};

beforeEach(() => {
  vi.clearAllMocks();
  server.use(
    http.get(`${API_BASE_URL}/attendance/admin/shift/configure/`, () =>
      HttpResponse.json({ configuration }),
    ),
  );
});

test("edits, adds and removes shifts, then saves the selected employment type", async () => {
  let savedBody;
  let currentConfiguration = configuration;
  server.use(
    http.get(`${API_BASE_URL}/attendance/admin/shift/configure/`, () =>
      HttpResponse.json({ configuration: currentConfiguration }),
    ),
    http.post(`${API_BASE_URL}/attendance/admin/shift/configure/`, async ({ request }) => {
      savedBody = await request.json();
      currentConfiguration = {
        ...configuration,
        PERMANENT: savedBody.shifts.map((shift, index) => ({ ...shift, id: index + 1 })),
      };
      return HttpResponse.json({ ok: true });
    }),
  );
  const user = userEvent.setup();
  render(<ShiftConfigurationPanel />);

  expect(await screen.findByText("Day Shift")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Configure Shifts" }));
  const nameFields = screen.getAllByPlaceholderText("e.g. Morning Shift");
  await user.clear(nameFields[0]);
  await user.type(nameFields[0], "Morning Shift");
  await user.clear(screen.getByPlaceholderText("e.g. MORN"));
  await user.type(screen.getByPlaceholderText("e.g. MORN"), "morn");
  await user.click(screen.getByRole("button", { name: "Add Shift" }));
  await user.type(screen.getAllByPlaceholderText("e.g. Morning Shift")[1], "Late Shift");
  await user.click(screen.getByRole("button", { name: "Remove shift 2" }));
  await user.click(screen.getByRole("button", { name: "Add Shift" }));
  await user.type(screen.getAllByPlaceholderText("e.g. Morning Shift")[1], "Late Shift");
  await user.click(screen.getByRole("button", { name: "Save Configuration" }));

  await waitFor(() =>
    expect(feedback.success).toHaveBeenCalledWith("Shift configuration saved successfully."),
  );
  expect(savedBody).toEqual({
    employment_type: "PERMANENT",
    shifts: [
      { name: "Morning Shift", code: "MORN", start_time: "09:00", end_time: "17:00" },
      { name: "Late Shift", code: "", start_time: "09:00", end_time: "17:00" },
    ],
  });
  expect(await screen.findByText("Morning Shift")).toBeInTheDocument();
  expect(screen.getByText("Late Shift")).toBeInTheDocument();
});

test("blocks invalid shifts and confirms before discarding changes or switching types", async () => {
  const confirm = vi.fn();
  vi.stubGlobal("confirm", confirm);
  const user = userEvent.setup();
  render(<ShiftConfigurationPanel />);
  await screen.findByText("Day Shift");
  await user.click(screen.getByRole("button", { name: "Configure Shifts" }));
  await user.clear(screen.getByPlaceholderText("e.g. Morning Shift"));
  await user.click(screen.getByRole("button", { name: "Save Configuration" }));
  expect(await screen.findByText("Shift 1: Name is required")).toBeInTheDocument();

  confirm.mockReturnValue(false);
  await user.click(screen.getByRole("button", { name: "INTERN" }));
  expect(screen.getByText("Configuring shifts for PERMANENT employees")).toBeInTheDocument();
  confirm.mockReturnValue(true);
  await user.click(screen.getByRole("button", { name: "INTERN" }));
  expect(screen.getByText("No shifts configured for INTERN employees.")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Configure Shifts" }));
  await user.click(screen.getByRole("button", { name: "Cancel" }));
  expect(confirm).toHaveBeenCalledWith("You have unsaved changes. Discard them?");
  expect(confirm).toHaveBeenCalledWith("Discard unsaved changes?");
  expect(screen.getByRole("button", { name: "Configure Shifts" })).toBeInTheDocument();
});

test("reports API errors when loading or saving shift configuration", async () => {
  server.use(
    http.get(`${API_BASE_URL}/attendance/admin/shift/configure/`, () =>
      HttpResponse.json({ detail: "Shift service unavailable" }, { status: 503 }),
    ),
  );
  const { unmount } = render(<ShiftConfigurationPanel />);
  expect(await screen.findByText("Shift service unavailable")).toBeInTheDocument();
  unmount();

  server.use(
    http.get(`${API_BASE_URL}/attendance/admin/shift/configure/`, () =>
      HttpResponse.json({ configuration }),
    ),
    http.post(`${API_BASE_URL}/attendance/admin/shift/configure/`, () =>
      HttpResponse.json({ detail: "Shift update rejected" }, { status: 400 }),
    ),
  );
  const user = userEvent.setup();
  render(<ShiftConfigurationPanel />);
  await screen.findByText("Day Shift");
  await user.click(screen.getByRole("button", { name: "Configure Shifts" }));
  await user.click(screen.getByRole("button", { name: "Save Configuration" }));
  await waitFor(() =>
    expect(feedback.notifyError).toHaveBeenCalledWith(
      expect.objectContaining({ message: "Shift update rejected" }),
      expect.objectContaining({ title: "Shift configuration failed" }),
    ),
  );
  expect(screen.getByText("Configuring shifts for PERMANENT employees")).toBeInTheDocument();
});
