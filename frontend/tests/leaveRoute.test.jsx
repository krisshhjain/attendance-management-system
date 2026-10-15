import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, expect, test, vi } from "vitest";
import { Route } from "../src/routes/leave.jsx";
import { FeedbackProvider } from "../src/feedback/FeedbackProvider.jsx";
import { OrganizationScopeProvider } from "../src/lib/organizationScope.jsx";
import { API_BASE_URL } from "../src/lib/api.js";
import { server } from "./mocks/server.js";

const uploadState = vi.hoisted(() => ({ upload: vi.fn() }));
const authState = vi.hoisted(() => ({ loginType: "employee" }));

vi.mock("@tanstack/react-router", () => ({ createFileRoute: () => (options) => options }));
vi.mock("../src/components/RequireAuth.jsx", () => ({
  RequireAuth: ({ children }) => children,
}));
vi.mock("../src/lib/useAuth.js", () => ({ useAuth: () => authState }));
vi.mock("../src/lib/api.js", async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, uploadFile: (...args) => uploadState.upload(...args) };
});

function renderPage() {
  const Component = Route.component;
  return render(
    <OrganizationScopeProvider>
      <FeedbackProvider>
        <Component />
      </FeedbackProvider>
    </OrganizationScopeProvider>,
  );
}

function leaveApi({ onSubmit = vi.fn(), onUpload = vi.fn(), attachment = "" } = {}) {
  let requests = [
    {
      id: 31,
      leave_type_name: "Medical",
      start_date: "2026-10-20",
      end_date: "2026-10-20",
      duration_days: 1,
      day_type: "FULL_DAY",
      reason: "Appointment",
      status: "PENDING",
      submitted_at: "2026-10-14T00:00:00Z",
      attachment,
    },
    {
      id: 32,
      leave_type_name: "Annual",
      start_date: "2026-11-02",
      end_date: "2026-11-03",
      duration_days: 2,
      day_type: "FULL_DAY",
      reason: "Travel",
      status: "APPROVED",
      submitted_at: "2026-10-13T00:00:00Z",
      attachment: "",
    },
    {
      id: 36,
      leave_type_name: "Annual",
      start_date: "2026-11-04",
      end_date: "2026-11-04",
      duration_days: 1,
      day_type: "FULL_DAY",
      reason: "Request denied",
      status: "DENIED",
      submitted_at: "2026-10-12T00:00:00Z",
      attachment: "",
    },
    {
      id: 37,
      leave_type_name: "Annual",
      start_date: "2026-11-05",
      end_date: "2026-11-05",
      duration_days: 1,
      day_type: "FULL_DAY",
      reason: "Request withdrawn",
      status: "CANCELLED",
      submitted_at: "2026-10-11T00:00:00Z",
      attachment: "",
    },
    {
      id: 38,
      leave_type_name: "Annual",
      start_date: "2026-11-06",
      end_date: "2026-11-06",
      duration_days: 1,
      day_type: "FULL_DAY",
      reason: "Legacy status",
      status: "OTHER",
      submitted_at: "2026-10-10T00:00:00Z",
      attachment: "",
    },
  ];
  server.use(
    http.get(`${API_BASE_URL}/leave/balances/`, () =>
      HttpResponse.json([
        {
          leave_type_id: "medical",
          leave_type_name: "Medical",
          leave_type_code: "MED",
          available: 4,
          annual_entitlement: 8,
          used: 2,
          pending: 1,
          is_paid: true,
          requires_document: true,
        },
      ]),
    ),
    http.get(`${API_BASE_URL}/leave/requests/`, () => HttpResponse.json(requests)),
    http.get(`${API_BASE_URL}/leave/types/`, () =>
      HttpResponse.json([
        { id: "medical", name: "Medical", code: "MED", is_paid: true, requires_document: true },
        { id: "annual", name: "Annual", code: "ANL", is_paid: true, requires_document: false },
      ]),
    ),
    http.post(`${API_BASE_URL}/leave/estimate-duration/`, () =>
      HttpResponse.json({ duration_days: 1.5 }),
    ),
    http.post(`${API_BASE_URL}/leave/upload/`, async ({ request }) => {
      const form = await request.formData();
      onUpload(form.get("file"));
      return HttpResponse.json({ file_url: "/media/medical-note.pdf" });
    }),
    http.post(`${API_BASE_URL}/leave/requests/`, async ({ request }) => {
      const payload = await request.json();
      onSubmit(payload);
      requests = [
        {
          id: 33,
          leave_type_name: "Medical",
          start_date: payload.start_date,
          end_date: payload.end_date,
          duration_days: 1,
          day_type: payload.day_type,
          reason: payload.reason,
          status: "PENDING",
          submitted_at: "2026-10-14T00:00:00Z",
          attachment: payload.attachment,
        },
        ...requests,
      ];
      return HttpResponse.json({ id: 33 }, { status: 201 });
    }),
    http.post(`${API_BASE_URL}/leave/requests/31/cancel/`, () => {
      requests = requests.filter((item) => item.id !== 31);
      return HttpResponse.json({ ok: true });
    }),
  );
  return { onSubmit, onUpload };
}

beforeEach(() => {
  authState.loginType = "employee";
});

test("filters employee requests and confirms cancellation before changing server state", async () => {
  leaveApi();
  const user = userEvent.setup();
  renderPage();

  expect(await screen.findByText("4 Left")).toBeInTheDocument();
  expect(screen.getByText("Appointment")).toBeInTheDocument();
  expect(screen.getByText("Travel")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "PENDING" }));
  expect(screen.getByText("Appointment")).toBeInTheDocument();
  expect(screen.queryByText("Travel")).not.toBeInTheDocument();

  const row = screen.getByText("Appointment").closest("tr");
  await user.click(within(row).getByRole("button", { name: "Cancel" }));
  expect(
    screen.getByText("Are you sure you want to cancel this pending leave request?"),
  ).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Confirm Cancellation" }));
  await waitFor(() => expect(screen.queryByText("Appointment")).not.toBeInTheDocument());
});

test("keeps the user informed when leave cancellation is rejected by the server", async () => {
  leaveApi();
  server.use(
    http.post(`${API_BASE_URL}/leave/requests/31/cancel/`, () =>
      HttpResponse.json({ detail: "Cancellation deadline has passed." }, { status: 400 }),
    ),
  );
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("Appointment");
  const row = screen.getByText("Appointment").closest("tr");
  await user.click(within(row).getByRole("button", { name: "Cancel" }));
  await user.click(screen.getByRole("button", { name: "Confirm Cancellation" }));

  expect(await screen.findByText("Cancellation deadline has passed.")).toBeInTheDocument();
  await waitFor(() =>
    expect(screen.queryByRole("button", { name: "Confirm Cancellation" })).not.toBeInTheDocument(),
  );
  expect(screen.getByText("Appointment")).toBeInTheDocument();
});

test("requires a supporting document for medical leave and rejects disallowed files", async () => {
  leaveApi();
  const user = userEvent.setup({ applyAccept: false });
  renderPage();
  await screen.findByText("4 Left");
  await user.click(screen.getByRole("button", { name: "Apply for Leave" }));
  expect(
    screen.getByText("This leave type requires supporting documentation."),
  ).toBeInTheDocument();
  await user.type(screen.getByRole("textbox", { name: "Reason for Leave" }), "Doctor visit");
  await user.click(screen.getByRole("button", { name: "Submit Request" }));
  expect(
    await screen.findByText("Supporting document is required for this leave type."),
  ).toBeInTheDocument();

  const input = document.getElementById("attachment-file-input");
  await user.upload(input, new File(["bad"], "script.exe", { type: "application/octet-stream" }));
  expect(
    await screen.findByText(
      "File type not allowed. Please upload PDF, JPG, PNG, DOC, or DOCX files.",
    ),
  ).toBeInTheDocument();
}, 15_000);

test("submits an eligible leave request with a supporting document link", async () => {
  const calls = leaveApi({ onSubmit: vi.fn(), onUpload: vi.fn() });
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("4 Left");
  await user.click(screen.getByRole("button", { name: "Apply for Leave" }));
  await user.type(screen.getByRole("textbox", { name: "Reason for Leave" }), "Medical appointment");
  await user.type(
    screen.getByRole("textbox", { name: "Or enter document URL/link" }),
    "https://files.example.test/doctor-note.pdf",
  );
  await user.click(screen.getByRole("button", { name: "Submit Request" }));

  await waitFor(() => expect(calls.onSubmit).toHaveBeenCalledOnce());
  expect(calls.onSubmit).toHaveBeenCalledWith(
    expect.objectContaining({
      leave_type: "medical",
      reason: "Medical appointment",
      attachment: "https://files.example.test/doctor-note.pdf",
    }),
  );
  expect(await screen.findByText("Leave request submitted successfully.")).toBeInTheDocument();
  expect(await screen.findByText("Medical appointment")).toBeInTheDocument();
}, 30_000);

test("uploads an allowed medical document before submitting the leave request", async () => {
  const calls = leaveApi({ onSubmit: vi.fn() });
  uploadState.upload.mockResolvedValue({ file_url: "/media/medical-note.pdf" });
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("4 Left");
  await user.click(screen.getByRole("button", { name: "Apply for Leave" }));
  await user.type(screen.getByRole("textbox", { name: "Reason for Leave" }), "Clinic visit");
  const file = new File(["test report"], "medical-note.pdf", { type: "application/pdf" });
  await user.upload(document.getElementById("attachment-file-input"), file);
  expect(await screen.findByText("Selected: medical-note.pdf")).toBeInTheDocument();
  expect(document.querySelector("form").checkValidity()).toBe(true);
  await user.click(screen.getByRole("button", { name: "Submit Request" }));

  await waitFor(() => expect(uploadState.upload).toHaveBeenCalledOnce());
  expect(uploadState.upload).toHaveBeenCalledWith(
    expect.objectContaining({ name: "medical-note.pdf" }),
  );
  expect(calls.onSubmit).toHaveBeenCalledWith(
    expect.objectContaining({ reason: "Clinic visit", attachment: "/media/medical-note.pdf" }),
  );
  expect(await screen.findByText("Leave request submitted successfully.")).toBeInTheDocument();
}, 30_000);

test("opens a remote image attachment in its document preview", async () => {
  leaveApi({ attachment: "https://files.example.test/medical-note.png" });
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("Appointment");
  await user.click(screen.getAllByRole("button", { name: "View Document" })[0]);
  expect(screen.getByText("Document for Medical Leave")).toBeInTheDocument();
  expect(screen.getByRole("img", { name: "Document preview" })).toHaveAttribute(
    "src",
    "https://files.example.test/medical-note.png",
  );
}, 15_000);

test("shows the server policy message when a leave request is rejected", async () => {
  leaveApi();
  server.use(
    http.post(`${API_BASE_URL}/leave/requests/`, () =>
      HttpResponse.json({ detail: "The notice period is too short." }, { status: 400 }),
    ),
  );
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("4 Left");
  await user.click(screen.getByRole("button", { name: "Apply for Leave" }));
  await user.type(screen.getByRole("textbox", { name: "Reason for Leave" }), "Medical visit");
  await user.type(
    screen.getByRole("textbox", { name: "Or enter document URL/link" }),
    "https://files.example.test/note.pdf",
  );
  await user.click(screen.getByRole("button", { name: "Submit Request" }));
  expect(await screen.findByText("The notice period is too short.")).toBeInTheDocument();
  expect(screen.getByRole("dialog")).toBeInTheDocument();
}, 30_000);

test("clamps leave dates to today and submits an allowed half-day request", async () => {
  const calls = leaveApi();
  const user = userEvent.setup();
  renderPage();
  await screen.findByText("4 Left");
  await user.click(screen.getByRole("button", { name: "Apply for Leave" }));

  const today = new Date();
  const todayKey = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
  const [start, end] = document.querySelectorAll('input[type="date"]');
  fireEvent.change(start, { target: { value: "2020-01-01" } });
  expect(start).toHaveValue(todayKey);
  fireEvent.change(end, { target: { value: "2020-01-01" } });
  expect(end).toHaveValue(todayKey);

  await user.click(screen.getByRole("combobox", { name: "Leave Type" }));
  await user.click(screen.getByRole("option", { name: /Annual \(ANL\)/ }));
  await user.click(screen.getByLabelText("First Half (0.5)"));
  await user.type(
    screen.getByRole("textbox", { name: "Reason for Leave" }),
    "Personal appointment",
  );
  await user.click(screen.getByRole("button", { name: "Submit Request" }));

  await waitFor(() =>
    expect(calls.onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ start_date: todayKey, end_date: todayKey, day_type: "FIRST_HALF" }),
    ),
  );
});

test("shows terminal request statuses and reports an unavailable admin employee list", async () => {
  leaveApi();
  authState.loginType = "systemadmin";
  server.use(
    http.get(`${API_BASE_URL}/admin/employees/list/`, () =>
      HttpResponse.json({ detail: "Employee directory unavailable." }, { status: 503 }),
    ),
  );
  renderPage();

  expect(await screen.findByText("Request denied")).toBeInTheDocument();
  expect(screen.getAllByText("DENIED").length).toBeGreaterThan(0);
  expect(screen.getAllByText("CANCELLED").length).toBeGreaterThan(0);
  expect(screen.getAllByText("OTHER").length).toBeGreaterThan(0);
  expect(await screen.findByText("Employee list unavailable")).toBeInTheDocument();
});
