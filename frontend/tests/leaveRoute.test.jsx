import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test, vi } from "vitest";
import { Route } from "../src/routes/leave.jsx";
import { FeedbackProvider } from "../src/feedback/FeedbackProvider.jsx";
import { OrganizationScopeProvider } from "../src/lib/organizationScope.jsx";
import { API_BASE_URL } from "../src/lib/api.js";
import { server } from "./mocks/server.js";

vi.mock("@tanstack/react-router", () => ({ createFileRoute: () => (options) => options }));
vi.mock("../src/components/RequireAuth.jsx", () => ({
  RequireAuth: ({ children }) => children,
}));
vi.mock("../src/lib/auth.jsx", () => ({ useAuth: () => ({ loginType: "employee" }) }));

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
}, 15_000);

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
}, 15_000);
