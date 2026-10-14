import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { API_BASE_URL } from "../src/lib/api.js";
import { NotificationBell } from "../src/components/notifications/NotificationBell.jsx";
import { server } from "./mocks/server.js";

const notifyError = vi.hoisted(() => vi.fn());
vi.mock("../src/feedback/FeedbackProvider.jsx", () => ({
  useFeedback: () => ({ notifyError }),
}));

const initialNotifications = [
  {
    id: 10,
    title: "Leave request updated",
    message: "Your leave request has been approved.",
    notification_type: "LEAVE",
    is_read: false,
    created_at: "2026-10-12T10:00:00Z",
  },
  {
    id: 11,
    title: "New device alert",
    message: "A new sign-in was detected.",
    notification_type: "ABSENCE_ALERT",
    is_read: false,
    created_at: "2026-10-12T11:00:00Z",
  },
];

function renderBell() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <NotificationBell />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  notifyError.mockClear();
  server.use(
    http.get(`${API_BASE_URL}/notifications/`, ({ request }) => {
      const unreadOnly = new URL(request.url).searchParams.get("unread") === "true";
      const results = unreadOnly
        ? initialNotifications.filter((item) => !item.is_read)
        : initialNotifications;
      return HttpResponse.json(results);
    }),
  );
});

test("opens unread alerts and marks leave decisions read through the notification action", async () => {
  let patchRequest;
  server.use(
    http.patch(`${API_BASE_URL}/notifications/:id/read/`, async ({ request, params }) => {
      patchRequest = { id: params.id, body: await request.json() };
      return HttpResponse.json({ ok: true });
    }),
  );
  const user = userEvent.setup();
  renderBell();

  await user.click(await screen.findByRole("button", { name: "Notifications, 2 unread" }));
  const dialog = await screen.findByRole("presentation");
  expect(within(dialog).getByText("2 unread")).toBeInTheDocument();
  expect(within(dialog).getByText("Your leave request has been approved.")).toBeInTheDocument();
  expect(within(dialog).getByText("ABSENCE ALERT")).toBeInTheDocument();

  await user.click(within(dialog).getByRole("button", { name: /Leave request updated/ }));
  await waitFor(() => expect(patchRequest).toEqual({ id: "10", body: {} }));
  expect(notifyError).not.toHaveBeenCalled();
});

test("retries failed notification loading and dismisses a system alert", async () => {
  let getCount = 0;
  let deleteCount = 0;
  server.use(
    http.get(`${API_BASE_URL}/notifications/`, ({ request }) => {
      if (new URL(request.url).searchParams.get("unread") === "true") {
        return HttpResponse.json(initialNotifications);
      }
      getCount += 1;
      return getCount === 1
        ? HttpResponse.json({ detail: "Temporarily unavailable" }, { status: 503 })
        : HttpResponse.json(initialNotifications);
    }),
    http.patch(`${API_BASE_URL}/notifications/:id/read/`, () => HttpResponse.json({ ok: true })),
    http.delete(`${API_BASE_URL}/notifications/:id/`, () => {
      deleteCount += 1;
      return new HttpResponse(null, { status: 204 });
    }),
  );
  const user = userEvent.setup();
  renderBell();
  await user.click(await screen.findByRole("button", { name: /Notifications/ }));
  expect(
    await screen.findByText("Notifications could not be loaded. Please try again."),
  ).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Try again" }));
  const alert = await screen.findByRole("button", { name: /New device alert/ });
  await user.click(alert);
  await waitFor(() => expect(deleteCount).toBe(1));
  expect(getCount).toBeGreaterThan(2);
});
