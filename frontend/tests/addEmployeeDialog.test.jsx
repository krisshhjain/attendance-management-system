import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { API_BASE_URL } from "../src/lib/api.js";
import { AddEmployeeDialog } from "../src/components/dashboard/AddEmployeeDialog.jsx";
import { server } from "./mocks/server.js";

const feedback = vi.hoisted(() => ({ success: vi.fn() }));
vi.mock("../src/feedback/FeedbackProvider.jsx", () => ({ useFeedback: () => feedback }));

beforeEach(() => vi.clearAllMocks());

test("creates an intern account with organization details and resets after success", async () => {
  const onClose = vi.fn();
  const onSuccess = vi.fn();
  let requestBody;
  server.use(
    http.post(`${API_BASE_URL}/admin/employees/`, async ({ request }) => {
      requestBody = await request.json();
      return HttpResponse.json({ id: 34 }, { status: 201 });
    }),
  );
  const user = userEvent.setup();
  render(<AddEmployeeDialog open onClose={onClose} onSuccess={onSuccess} />);
  const dialog = screen.getByRole("dialog");

  await user.type(within(dialog).getByLabelText(/First Name/), "Riya");
  await user.type(within(dialog).getByLabelText(/Last Name/), "Shah");
  await user.type(within(dialog).getByLabelText(/Email Address/), "riya@example.test");
  await user.type(within(dialog).getByLabelText(/Temporary Password/), "TempPass1!");
  await user.type(within(dialog).getByLabelText(/Department/), "Engineering");
  await user.click(within(dialog).getByRole("combobox", { name: "Employment Type" }));
  await user.click(screen.getByRole("option", { name: "INTERN" }));
  await user.type(within(dialog).getByLabelText(/Section/), "A");
  await user.type(within(dialog).getByLabelText(/Subsection/), "A1");
  fireEvent.change(within(dialog).getByLabelText(/Date Joined/), {
    target: { value: "2026-10-01" },
  });
  await user.click(within(dialog).getByRole("button", { name: "Create" }));

  await waitFor(() => expect(onSuccess).toHaveBeenCalledOnce());
  expect(requestBody).toEqual({
    first_name: "Riya",
    last_name: "Shah",
    email: "riya@example.test",
    password: "TempPass1!",
    department: "Engineering",
    section: "A",
    subsection: "A1",
    employment_type: "INTERN",
    date_joined: "2026-10-01",
  });
  expect(feedback.success).toHaveBeenCalledWith("Employee created successfully.");
  expect(within(dialog).getByLabelText(/First Name/)).toHaveValue("");
  expect(onClose).not.toHaveBeenCalled();
});

test("shows server validation feedback and keeps the form available to correct it", async () => {
  const onSuccess = vi.fn();
  server.use(
    http.post(`${API_BASE_URL}/admin/employees/`, () =>
      HttpResponse.json({ detail: "An account already uses this email." }, { status: 400 }),
    ),
  );
  const user = userEvent.setup();
  render(<AddEmployeeDialog open onClose={vi.fn()} onSuccess={onSuccess} />);
  const dialog = screen.getByRole("dialog");
  await user.type(within(dialog).getByLabelText(/First Name/), "Riya");
  await user.type(within(dialog).getByLabelText(/Email Address/), "taken@example.test");
  await user.type(within(dialog).getByLabelText(/Temporary Password/), "TempPass1!");
  await user.click(within(dialog).getByRole("button", { name: "Create" }));

  expect(
    await within(dialog).findByText("An account already uses this email."),
  ).toBeInTheDocument();
  expect(within(dialog).getByLabelText(/Email Address/)).toHaveValue("taken@example.test");
  expect(onSuccess).not.toHaveBeenCalled();
});

test("closes the creation dialog when the user cancels", async () => {
  const onClose = vi.fn();
  const user = userEvent.setup();
  render(<AddEmployeeDialog open onClose={onClose} onSuccess={vi.fn()} />);
  await user.click(screen.getByRole("button", { name: "Cancel" }));
  expect(onClose).toHaveBeenCalledOnce();
});
