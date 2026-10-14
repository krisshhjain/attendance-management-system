import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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

test("approves a pending leave request and refreshes the review queue", async () => {
  const user = userEvent.setup();
  renderPage();
  expect(await screen.findByText("Avery Lee")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Approve" }));
  await user.click(screen.getByRole("button", { name: "Confirm Action" }));
  await waitFor(() => expect(state.api.approveLeaveRequest).toHaveBeenCalledWith(9, ""));
  expect(state.success).toHaveBeenCalledWith("Leave approved successfully.");
  expect(state.api.fetchAdminLeaveRequests).toHaveBeenCalledTimes(2);
}, 15_000);

test("opens and closes an attached document from an admin leave review row", async () => {
  const [request] = await state.api.fetchAdminLeaveRequests();
  state.api.fetchAdminLeaveRequests.mockResolvedValue([
    { ...request, attachment: "https://files.example.test/medical-note.png" },
  ]);
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("Avery Lee");
  await user.click(screen.getByRole("button", { name: "View Document" }));

  expect(screen.getByText("Document for Avery Lee - Annual Leave Leave")).toBeInTheDocument();
  expect(screen.getByRole("img", { name: "Document preview" })).toHaveAttribute(
    "src",
    "https://files.example.test/medical-note.png",
  );
  await user.click(screen.getByRole("button", { name: "Close" }));
  expect(screen.queryByRole("img", { name: "Document preview" })).not.toBeInTheDocument();
});

test("filters leave reviews by server status and renders the available decisions", async () => {
  const [request] = await state.api.fetchAdminLeaveRequests();
  state.api.fetchAdminLeaveRequests.mockResolvedValue([
    request,
    { ...request, id: 10, employee_name: "Blake Park", status: "APPROVED" },
    { ...request, id: 11, employee_name: "Casey Reed", status: "DENIED" },
    { ...request, id: 12, employee_name: "Drew Cole", status: "CANCELLED" },
    { ...request, id: 13, employee_name: "Elliot Gray", status: "OTHER" },
  ]);
  const user = userEvent.setup();
  renderPage();

  expect(await screen.findByText("Blake Park")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "ALL" }));
  await waitFor(() => expect(state.api.fetchAdminLeaveRequests).toHaveBeenLastCalledWith({}));
  expect(screen.getByText("Casey Reed")).toBeInTheDocument();
  expect(screen.getByText("Drew Cole")).toBeInTheDocument();
  expect(screen.getByText("OTHER")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "APPROVED" }));
  await waitFor(() =>
    expect(state.api.fetchAdminLeaveRequests).toHaveBeenLastCalledWith({ status: "APPROVED" }),
  );
});

test("cancels an approved leave request and refreshes the review queue", async () => {
  const [request] = await state.api.fetchAdminLeaveRequests();
  state.api.fetchAdminLeaveRequests.mockResolvedValue([{ ...request, status: "APPROVED" }]);
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("Avery Lee");

  await user.click(screen.getByRole("button", { name: "Cancel Approved" }));
  expect(screen.getByText("Cancel Approved Leave")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Confirm Action" }));

  await waitFor(() => expect(state.api.cancelApprovedLeaveRequest).toHaveBeenCalledWith(9));
  expect(state.success).toHaveBeenCalledWith("Leave cancelled successfully.");
  expect(state.api.fetchAdminLeaveRequests).toHaveBeenCalledTimes(3);
});

test("reports a failed leave decision without discarding the review dialog", async () => {
  state.api.approveLeaveRequest.mockRejectedValue(new Error("Approval service is unavailable"));
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("Avery Lee");
  await user.click(screen.getByRole("button", { name: "Approve" }));
  await user.click(screen.getByRole("button", { name: "Confirm Action" }));

  await waitFor(() =>
    expect(state.notifyError).toHaveBeenCalledWith(
      expect.objectContaining({ message: "Approval service is unavailable" }),
      expect.objectContaining({ title: "Leave action failed" }),
    ),
  );
  expect(screen.getByText("Approve Leave Request")).toBeInTheDocument();
});

test("shows a server validation error when an office location cannot be saved", async () => {
  state.api.createOfficeLocation.mockRejectedValue(new Error("Location name already exists"));
  const user = userEvent.setup();
  renderPage();
  await user.click(screen.getByRole("tab", { name: "Office Locations" }));
  await user.click(await screen.findByRole("button", { name: "Add Location" }));
  await user.type(screen.getByRole("textbox", { name: "Location Name" }), "Portland Office");
  await user.type(screen.getByRole("spinbutton", { name: "Latitude" }), "45.5");
  await user.type(screen.getByRole("spinbutton", { name: "Longitude" }), "-122.6");
  await user.click(screen.getByRole("button", { name: "Save Location" }));

  expect(await screen.findByText("Location name already exists")).toBeInTheDocument();
  expect(state.api.createOfficeLocation).toHaveBeenCalledWith(
    expect.objectContaining({ name: "Portland Office", latitude: 45.5, longitude: -122.6 }),
  );
});

test("denies administration access to a signed-in non-staff user", () => {
  state.user = { is_staff: false, is_superuser: false, is_system_admin: false };
  state.loginType = "employee";
  renderPage();

  expect(screen.getByRole("heading", { name: "Access Denied" })).toBeInTheDocument();
  expect(
    screen.getByText("You do not have administrative permissions to view this page."),
  ).toBeInTheDocument();
  expect(state.api.fetchAdminLeaveRequests).not.toHaveBeenCalled();
});

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
}, 15_000);

test("edits an office location and saves normalized field values", async () => {
  state.api.fetchOfficeLocations.mockResolvedValue([
    {
      id: 17,
      name: "Portland Office",
      latitude: 45.52,
      longitude: -122.68,
      radius_meters: 200,
      is_active: false,
    },
  ]);
  const user = userEvent.setup();
  renderPage();
  await user.click(screen.getByRole("tab", { name: "Office Locations" }));
  const row = (await screen.findByText("Portland Office")).closest("tr");
  await user.click(within(row).getAllByRole("button")[0]);

  expect(screen.getByRole("heading", { name: "Edit Office Location" })).toBeInTheDocument();
  await user.clear(screen.getByRole("textbox", { name: "Location Name" }));
  await user.type(screen.getByRole("textbox", { name: "Location Name" }), "  Portland HQ  ");
  await user.clear(screen.getByRole("spinbutton", { name: "Radius (meters)" }));
  await user.type(screen.getByRole("spinbutton", { name: "Radius (meters)" }), "250");
  await user.click(screen.getByRole("button", { name: "Save Location" }));

  await waitFor(() =>
    expect(state.api.updateOfficeLocation).toHaveBeenCalledWith(17, {
      name: "Portland HQ",
      latitude: 45.52,
      longitude: -122.68,
      radius_meters: 250,
      is_active: false,
    }),
  );
  expect(state.success).toHaveBeenCalledWith("Office location updated successfully.");
  expect(state.api.fetchOfficeLocations).toHaveBeenCalledTimes(2);
});

test("honors office location deletion confirmation before refreshing the list", async () => {
  state.api.fetchOfficeLocations.mockResolvedValue([
    {
      id: 21,
      name: "Austin Office",
      latitude: 30,
      longitude: -97,
      radius_meters: 150,
      is_active: true,
    },
  ]);
  const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
  const user = userEvent.setup();
  renderPage();
  await user.click(screen.getByRole("tab", { name: "Office Locations" }));
  const row = (await screen.findByText("Austin Office")).closest("tr");
  const buttons = within(row).getAllByRole("button");

  await user.click(buttons[1]);
  expect(confirm).toHaveBeenCalledWith("Delete office location 'Austin Office'?");
  expect(state.api.deleteOfficeLocation).not.toHaveBeenCalled();

  confirm.mockReturnValue(true);
  await user.click(buttons[1]);
  await waitFor(() => expect(state.api.deleteOfficeLocation).toHaveBeenCalledWith(21));
  expect(state.success).toHaveBeenCalledWith("Office location deleted successfully.");
  expect(state.api.fetchOfficeLocations).toHaveBeenCalledTimes(2);
  confirm.mockRestore();
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
}, 15_000);

test("updates an existing leave type and refreshes the registry", async () => {
  const user = userEvent.setup();
  state.api.fetchLeaveTypesAll.mockResolvedValue([
    {
      id: 7,
      name: "Casual Leave",
      code: "CAS",
      description: "Personal days",
      is_paid: true,
      allow_half_day: true,
      allow_past_dates: false,
      allow_future_dates: true,
      min_notice_days: 1,
      requires_document: false,
      is_active: true,
    },
  ]);
  renderPage();
  await user.click(screen.getByRole("tab", { name: "Leave Types" }));
  await user.click(await screen.findByRole("button", { name: "Edit leave type" }));
  await user.clear(screen.getByRole("textbox", { name: "Name" }));
  await user.type(screen.getByRole("textbox", { name: "Name" }), "Personal Leave");
  await user.clear(screen.getByRole("textbox", { name: "Code" }));
  await user.type(screen.getByRole("textbox", { name: "Code" }), "personal");
  await user.click(screen.getByRole("button", { name: "Save Leave Type" }));

  await waitFor(() =>
    expect(state.api.updateLeaveType).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ name: "Personal Leave", code: "PERSONAL" }),
    ),
  );
  expect(state.success).toHaveBeenCalledWith("Leave type updated successfully.");
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

test("edits policy controls and submits the complete updated policy payload", async () => {
  const user = userEvent.setup();
  state.api.fetchLeaveTypesAll.mockResolvedValue([{ id: 4, name: "Annual Leave", code: "ANNUAL" }]);
  state.api.fetchLeavePoliciesAll.mockResolvedValue([
    {
      id: 15,
      employee_type: "PERMANENT",
      leave_type: 4,
      leave_type_name: "Annual Leave",
      leave_type_code: "ANNUAL",
      annual_entitlement: 20,
      allow_carry_forward: false,
      max_carry_forward: 0,
      max_consecutive_days: 10,
      min_notice_days: 2,
      allow_half_day: true,
      requires_document: false,
      effective_from: "2026-01-01",
      is_active: true,
    },
  ]);
  renderPage();
  await user.click(screen.getByRole("tab", { name: "Leave Policies" }));
  const row = (await screen.findByText("Annual Leave")).closest("tr");
  await user.click(within(row).getByRole("button", { name: "Edit policy" }));

  fireEvent.change(screen.getByRole("spinbutton", { name: "Annual Entitlement (days per year)" }), {
    target: { value: "24" },
  });
  await user.click(screen.getByRole("checkbox", { name: "Allow Carry Forward to Next Year" }));
  await user.type(screen.getByRole("spinbutton", { name: "Max Carry Forward Days" }), "4");
  await user.click(screen.getByRole("checkbox", { name: "Require Document" }));
  await user.click(screen.getByRole("button", { name: "Save Policy" }));

  await waitFor(() =>
    expect(state.api.updateLeavePolicy).toHaveBeenCalledWith(
      15,
      expect.objectContaining({
        employee_type: "PERMANENT",
        leave_type: 4,
        annual_entitlement: 24,
        allow_carry_forward: true,
        max_carry_forward: 4,
        max_consecutive_days: 10,
        min_notice_days: 2,
        allow_half_day: true,
        requires_document: true,
        effective_from: "2026-01-01",
        is_active: true,
      }),
    ),
  );
  expect(state.success).toHaveBeenCalledWith("Leave policy updated successfully.");
});

test("limits system administrators to read-only policy and leave-type tabs", async () => {
  state.loginType = "systemadmin";
  state.user = { is_staff: true, is_system_admin: true, is_superuser: false };
  state.api.fetchLeavePoliciesAll.mockResolvedValue([
    {
      id: 16,
      employee_type: "PERMANENT",
      leave_type: 4,
      leave_type_name: "Annual Leave",
      leave_type_code: "ANNUAL",
      annual_entitlement: 20,
      allow_carry_forward: false,
      max_carry_forward: 0,
      max_consecutive_days: 10,
      min_notice_days: 0,
      allow_half_day: true,
      requires_document: false,
      effective_from: "2026-01-01",
      is_active: true,
    },
  ]);
  const user = userEvent.setup();
  renderPage();

  expect(screen.queryByRole("tab", { name: "Office Locations" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("tab", { name: "Leave Policies (View Only)" }));
  expect(await screen.findByText("Annual Leave")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Configure New Policy" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Edit policy" })).not.toBeInTheDocument();

  await user.click(screen.getByRole("tab", { name: "Leave Types (View Only)" }));
  expect(await screen.findByText("System Leave Types Registry")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Create Leave Type" })).not.toBeInTheDocument();
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

test("confirms before deactivating a leave policy", async () => {
  const user = userEvent.setup();
  state.api.fetchLeavePoliciesAll.mockResolvedValue([
    {
      id: 12,
      employee_type: "PERMANENT",
      leave_type: 4,
      leave_type_name: "Annual Leave",
      leave_type_code: "ANNUAL",
      annual_entitlement: 20,
      allow_carry_forward: false,
      max_carry_forward: 0,
      max_consecutive_days: 10,
      min_notice_days: 0,
      allow_half_day: true,
      requires_document: false,
      effective_from: "2026-01-01",
      is_active: true,
    },
  ]);
  renderPage();
  await user.click(screen.getByRole("tab", { name: "Leave Policies" }));
  expect(await screen.findByText("Annual Leave")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Deactivate policy" }));
  expect(screen.getByText("Annual Leave (PERMANENT)")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Deactivate" }));
  await waitFor(() => expect(state.api.deleteLeavePolicy).toHaveBeenCalledWith(12));
  expect(state.success).toHaveBeenCalledWith("Leave policy deactivated successfully.");
});
