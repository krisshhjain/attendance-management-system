import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, test } from "vitest";
import { HolidayManagementPanel } from "../src/components/HolidayManagementPanel.jsx";
import { API_BASE_URL } from "../src/lib/api.js";
import { server } from "./mocks/server.js";

function renderPanel() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <HolidayManagementPanel />
    </QueryClientProvider>,
  );
}

test("creates a holiday and refreshes the admin calendar", async () => {
  let holidays = [];
  let createdPayload;
  server.use(
    http.get(`${API_BASE_URL}/holidays/admin/`, () => HttpResponse.json(holidays)),
    http.post(`${API_BASE_URL}/holidays/admin/`, async ({ request }) => {
      createdPayload = await request.json();
      holidays = [{ id: 1, ...createdPayload, is_active: true }];
      return HttpResponse.json(holidays[0], { status: 201 });
    }),
  );
  const user = userEvent.setup();
  renderPanel();

  expect(await screen.findByText("No holidays have been added.")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Add holiday" }));
  await user.type(screen.getByLabelText("Holiday date"), "2026-12-25");
  await user.type(screen.getByRole("textbox", { name: "Holiday name" }), "Winter closure");
  await user.click(screen.getByRole("button", { name: "Save" }));

  expect(await screen.findByText("Winter closure")).toBeInTheDocument();
  expect(createdPayload).toEqual({ date: "2026-12-25", name: "Winter closure" });
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
});

test("edits an existing holiday and toggles its active state through PATCH actions", async () => {
  let holiday = { id: 4, date: "2026-01-26", name: "Republic Day", is_active: true };
  const patches = [];
  server.use(
    http.get(`${API_BASE_URL}/holidays/admin/`, () => HttpResponse.json([holiday])),
    http.patch(`${API_BASE_URL}/holidays/admin/4/`, async ({ request }) => {
      const patch = await request.json();
      patches.push(patch);
      holiday = { ...holiday, ...patch };
      return HttpResponse.json(holiday);
    }),
  );
  const user = userEvent.setup();
  renderPanel();
  const row = (await screen.findByText("Republic Day")).closest("tr");

  await user.click(within(row).getByRole("button", { name: "Edit Republic Day" }));
  await user.clear(screen.getByLabelText("Holiday date"));
  await user.type(screen.getByLabelText("Holiday date"), "2026-01-27");
  await user.clear(screen.getByRole("textbox", { name: "Holiday name" }));
  await user.type(screen.getByRole("textbox", { name: "Holiday name" }), "Founders Day");
  await user.click(screen.getByRole("button", { name: "Save" }));
  await screen.findByText("Founders Day");
  expect(patches[0]).toEqual({ date: "2026-01-27", name: "Founders Day" });
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());

  const updatedRow = screen.getByText("Founders Day").closest("tr");
  await user.click(within(updatedRow).getByRole("checkbox", { name: "Deactivate Founders Day" }));
  await waitFor(() => expect(patches[1]).toEqual({ is_active: false }));
  expect(screen.getByText("Inactive")).toBeInTheDocument();
});

test("surfaces admin holiday load failures and lets the user dismiss the message", async () => {
  server.use(
    http.get(`${API_BASE_URL}/holidays/admin/`, () =>
      HttpResponse.json({ detail: "Holiday service unavailable" }, { status: 503 }),
    ),
  );
  const user = userEvent.setup();
  renderPanel();

  expect(await screen.findByText("Holiday service unavailable")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Close" }));
  expect(screen.queryByText("Holiday service unavailable")).not.toBeInTheDocument();
});
