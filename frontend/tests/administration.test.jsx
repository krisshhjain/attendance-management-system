import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { Route } from "../src/routes/administration.jsx";

const state = vi.hoisted(() => ({
  user: { is_superuser: true, is_staff: true },
  loginType: "admin",
  api: {},
  success: vi.fn(),
  notifyError: vi.fn(),
}));
vi.mock("@tanstack/react-router", () => ({ createFileRoute: () => (options) => options }));
vi.mock("../src/components/RequireAuth.jsx", () => ({ RequireAuth: ({ children }) => children }));
vi.mock("../src/components/ShiftConfigurationPanel.jsx", () => ({
  ShiftConfigurationPanel: () => null,
}));
vi.mock("../src/components/ManagerManagement.jsx", () => ({ ManagerManagement: () => null }));
vi.mock("../src/components/HolidayManagementPanel.jsx", () => ({
  HolidayManagementPanel: () => null,
}));
vi.mock("../src/lib/auth.jsx", () => ({
  useAuth: () => ({ user: state.user, loginType: state.loginType }),
}));
vi.mock("../src/feedback/FeedbackProvider.jsx", () => ({
  useFeedback: () => ({ success: state.success, notifyError: state.notifyError }),
}));
vi.mock("../src/lib/api.js", () => ({
  fetchAdminLeaveRequests: (...args) => state.api.fetchAdminLeaveRequests(...args),
  approveLeaveRequest: (...args) => state.api.approveLeaveRequest(...args),
  denyLeaveRequest: (...args) => state.api.denyLeaveRequest(...args),
  cancelApprovedLeaveRequest: (...args) => state.api.cancelApprovedLeaveRequest(...args),
  fetchAdminLeaveBalances: (...args) => state.api.fetchAdminLeaveBalances(...args),
  fetchLeaveTypesAll: (...args) => state.api.fetchLeaveTypesAll(...args),
  createLeaveType: (...args) => state.api.createLeaveType(...args),
  updateLeaveType: (...args) => state.api.updateLeaveType(...args),
  deleteLeaveType: (...args) => state.api.deleteLeaveType(...args),
  fetchLeavePoliciesAll: (...args) => state.api.fetchLeavePoliciesAll(...args),
  createLeavePolicy: (...args) => state.api.createLeavePolicy(...args),
  updateLeavePolicy: (...args) => state.api.updateLeavePolicy(...args),
  deleteLeavePolicy: (...args) => state.api.deleteLeavePolicy(...args),
  fetchOfficeLocations: (...args) => state.api.fetchOfficeLocations(...args),
  createOfficeLocation: (...args) => state.api.createOfficeLocation(...args),
  updateOfficeLocation: (...args) => state.api.updateOfficeLocation(...args),
  deleteOfficeLocation: (...args) => state.api.deleteOfficeLocation(...args),
}));

function renderPage() {
  const Component = Route.component;
  return render(<Component />);
}

beforeEach(() => {
  vi.clearAllMocks();
  state.user = { is_superuser: true, is_staff: true };
  state.loginType = "admin";
  state.api = {
    fetchAdminLeaveRequests: vi.fn().mockResolvedValue([
      {
        id: 9,
        employee_name: "Avery Lee",
        employee_email: "avery@example.test",
        employment_type: "PERMANENT",
        employee_department: "People",
        leave_type_name: "Annual Leave",
        start_date: "2026-11-02",
        end_date: "2026-11-02",
        duration_days: 1,
        day_type: "FULL_DAY",
        reason: "Family event",
        status: "PENDING",
      },
    ]),
    approveLeaveRequest: vi.fn().mockResolvedValue({}),
    denyLeaveRequest: vi.fn().mockResolvedValue({}),
    cancelApprovedLeaveRequest: vi.fn().mockResolvedValue({}),
    fetchAdminLeaveBalances: vi.fn().mockResolvedValue([]),
    fetchLeaveTypesAll: vi.fn().mockResolvedValue([]),
    createLeaveType: vi.fn().mockResolvedValue({}),
    updateLeaveType: vi.fn().mockResolvedValue({}),
    deleteLeaveType: vi.fn().mockResolvedValue({}),
    fetchLeavePoliciesAll: vi.fn().mockResolvedValue([]),
    createLeavePolicy: vi.fn().mockResolvedValue({}),
    updateLeavePolicy: vi.fn().mockResolvedValue({}),
    deleteLeavePolicy: vi.fn().mockResolvedValue({}),
    fetchOfficeLocations: vi.fn().mockResolvedValue([]),
    createOfficeLocation: vi.fn().mockResolvedValue({}),
    updateOfficeLocation: vi.fn().mockResolvedValue({}),
    deleteOfficeLocation: vi.fn().mockResolvedValue({}),
  };
});

test("requires reviewer notes to deny a request and submits the final decision", async () => {
  const user = userEvent.setup();
  renderPage();
  expect(await screen.findByText("Avery Lee")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Deny" }));
  await user.click(screen.getByRole("button", { name: "Confirm Action" }));
  expect(
    await screen.findByText("Reviewer remarks are required when denying a leave request."),
  ).toBeInTheDocument();

  await user.type(
    screen.getByRole("textbox", { name: "Reviewer Remarks (Required)" }),
    "Dates conflict with policy",
  );
  await user.click(screen.getByRole("button", { name: "Confirm Action" }));
  await waitFor(() =>
    expect(state.api.denyLeaveRequest).toHaveBeenCalledWith(9, "Dates conflict with policy"),
  );
  expect(state.success).toHaveBeenCalledWith("Leave rejected successfully.");
}, 15_000);

test("validates office coordinates before creating a location and refreshes the list", async () => {
  const user = userEvent.setup();
  renderPage();
  await user.click(screen.getByRole("tab", { name: "Office Locations" }));
  expect(await screen.findByText("Workplace Office Locations")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Add Location" }));
  await user.type(screen.getByRole("textbox", { name: "Location Name" }), "Seattle Office");
  await user.type(screen.getByRole("spinbutton", { name: "Latitude" }), "91");
  await user.type(screen.getByRole("spinbutton", { name: "Longitude" }), "-122");
  await user.click(screen.getByRole("button", { name: "Save Location" }));
  expect(
    await screen.findByText("Enter a name, valid coordinates, and a positive radius."),
  ).toBeInTheDocument();
  expect(state.api.createOfficeLocation).not.toHaveBeenCalled();

  await user.clear(screen.getByRole("spinbutton", { name: "Latitude" }));
  await user.type(screen.getByRole("spinbutton", { name: "Latitude" }), "47.6");
  await user.click(screen.getByRole("button", { name: "Save Location" }));
  await waitFor(() =>
    expect(state.api.createOfficeLocation).toHaveBeenCalledWith({
      name: "Seattle Office",
      latitude: 47.6,
      longitude: -122,
      radius_meters: 150,
      is_active: true,
    }),
  );
  expect(state.success).toHaveBeenCalledWith("Office location created successfully.");
  expect(state.api.fetchOfficeLocations).toHaveBeenCalledTimes(2);
});

test("creates a normalized leave type from the registry", async () => {
  const user = userEvent.setup();
  renderPage();
  await user.click(screen.getByRole("tab", { name: "Leave Types" }));
  await screen.findByText("System Leave Types Registry");
  await user.click(screen.getByRole("button", { name: "Create Leave Type" }));
  await user.type(screen.getByRole("textbox", { name: "Name" }), "  Volunteer Leave  ");
  await user.type(screen.getByRole("textbox", { name: "Code" }), " vol ");
  await user.type(screen.getByRole("textbox", { name: "Description" }), "Community service");
  await user.click(screen.getByRole("button", { name: "Save Leave Type" }));
  await waitFor(() =>
    expect(state.api.createLeaveType).toHaveBeenCalledWith({
      name: "Volunteer Leave",
      code: "VOL",
      description: "Community service",
      is_paid: true,
      allow_half_day: true,
      allow_past_dates: true,
      allow_future_dates: true,
      min_notice_days: 0,
      requires_document: false,
      is_active: true,
    }),
  );
  expect(state.success).toHaveBeenCalledWith("Leave type created successfully.");
});

test("creates a leave policy for a selected leave type", async () => {
  const user = userEvent.setup();
  state.api.fetchLeaveTypesAll.mockResolvedValue([{ id: 4, name: "Annual Leave", code: "ANNUAL" }]);
  renderPage();
  await user.click(screen.getByRole("tab", { name: "Leave Policies" }));
  await screen.findByText("Leave Policies");
  await user.click(screen.getByRole("button", { name: "Configure New Policy" }));
  await user.click(screen.getByRole("button", { name: "Save Policy" }));
  await waitFor(() =>
    expect(state.api.createLeavePolicy).toHaveBeenCalledWith(
      expect.objectContaining({
        employee_type: "PERMANENT",
        leave_type: 4,
        annual_entitlement: 12,
        max_consecutive_days: 10,
        min_notice_days: 0,
        allow_carry_forward: false,
      }),
    ),
  );
  expect(state.success).toHaveBeenCalledWith("Leave policy created successfully.");
});

test("filters the employee leave balance audit by email", async () => {
  const user = userEvent.setup();
  state.api.fetchAdminLeaveBalances.mockResolvedValue([
    {
      employee_id: 1,
      employee_email: "avery@example.test",
      employment_type: "PERMANENT",
      balances: [
        {
          leave_type_id: 2,
          leave_type_name: "Annual Leave",
          leave_type_code: "ANNUAL",
          annual_entitlement: 20,
          carried_forward: 2,
          used: 4,
          pending: 1,
          available: 17,
        },
      ],
    },
    {
      employee_id: 2,
      employee_email: "blake@example.test",
      employment_type: "CONTRACT",
      balances: [],
    },
  ]);
  renderPage();
  await user.click(screen.getByRole("tab", { name: "Employee Balances" }));
  expect(await screen.findByText("avery@example.test")).toBeInTheDocument();
  expect(screen.getByText("blake@example.test")).toBeInTheDocument();
  await user.type(screen.getByPlaceholderText("Filter by employee email..."), "avery");
  expect(screen.getByText("avery@example.test")).toBeInTheDocument();
  expect(screen.queryByText("blake@example.test")).not.toBeInTheDocument();
  expect(screen.getByText("17")).toBeInTheDocument();
});
