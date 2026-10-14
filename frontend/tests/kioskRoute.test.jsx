import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, test, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { API_BASE_URL } from "../src/lib/api.js";
import { Route } from "../src/routes/kiosk.jsx";
import { server } from "./mocks/server.js";

const feedback = vi.hoisted(() => ({ success: vi.fn(), info: vi.fn() }));
vi.mock("@tanstack/react-router", () => ({ createFileRoute: () => (options) => options }));
vi.mock("../src/feedback/FeedbackProvider.jsx", () => ({ useFeedback: () => feedback }));
vi.mock("../src/components/WebcamCapture.jsx", () => ({
  default: ({ onCapture, onCancel, isLoading }) => (
    <div>
      <button disabled={isLoading} onClick={() => onCapture(["frame-one", "frame-two"], 123456)}>
        Capture &amp; Verify
      </button>
      <button onClick={onCancel}>Cancel capture</button>
    </div>
  ),
}));
vi.mock("../src/components/FaceResultOverlay.jsx", () => ({
  default: ({ title, message, onRetry, onClose }) => (
    <section aria-label="Attendance result">
      <h2>{title}</h2>
      <p>{message}</p>
      <button onClick={onRetry}>Try again</button>
      <button onClick={onClose}>Close result</button>
    </section>
  ),
}));

beforeEach(() => {
  vi.clearAllMocks();
  server.use(
    http.post(`${API_BASE_URL}/attendance/kiosk/check-in/`, () => HttpResponse.json({ ok: true })),
    http.post(`${API_BASE_URL}/attendance/kiosk/check-out/`, () => HttpResponse.json({ ok: true })),
  );
});

function renderKiosk() {
  const Component = Route.component;
  return render(<Component />);
}

test("marks a kiosk check-in from captured frames and announces completion", async () => {
  let payload;
  let headers;
  server.use(
    http.post(`${API_BASE_URL}/attendance/kiosk/check-in/`, async ({ request }) => {
      payload = await request.json();
      headers = request.headers;
      return HttpResponse.json({ ok: true });
    }),
  );
  const user = userEvent.setup();
  renderKiosk();

  await user.click(screen.getByRole("button", { name: "Check In" }));
  expect(feedback.info).toHaveBeenCalledWith("Press Capture & Verify to check in.");
  await user.click(screen.getByRole("button", { name: "Capture & Verify" }));

  expect(await screen.findByRole("heading", { name: "Face verified" })).toBeInTheDocument();
  expect(payload).toEqual({ frames: ["frame-one", "frame-two"], captured_at_ms: 123456 });
  expect(headers.get("authorization")).toBeNull();
  await waitFor(
    () => expect(feedback.success).toHaveBeenCalledWith("Attendance marked successfully."),
    { timeout: 5000 },
  );
  expect(screen.queryByRole("heading", { name: "Face verified" })).not.toBeInTheDocument();
});

test("uses the check-out endpoint and lets a person retry liveness verification", async () => {
  let calls = 0;
  server.use(
    http.post(`${API_BASE_URL}/attendance/kiosk/check-out/`, () => {
      calls += 1;
      return calls === 1
        ? HttpResponse.json({ error: "Liveness check failed for this image." }, { status: 400 })
        : HttpResponse.json({ ok: true });
    }),
  );
  const user = userEvent.setup();
  renderKiosk();

  await user.click(screen.getByRole("button", { name: "Check Out" }));
  expect(feedback.info).toHaveBeenCalledWith("Press Capture & Verify to check out.");
  await user.click(screen.getByRole("button", { name: "Capture & Verify" }));
  const result = screen.getByRole("region", { name: "Attendance result" });
  expect(within(result).getByRole("heading", { name: "Face not verified" })).toBeInTheDocument();
  expect(
    within(result).getByText(/live camera image\. Please try again using the kiosk camera/),
  ).toBeInTheDocument();
  await user.click(within(result).getByRole("button", { name: "Try again" }));
  expect(screen.queryByRole("region", { name: "Attendance result" })).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Capture & Verify" }));
  expect(await screen.findByRole("heading", { name: "Face verified" })).toBeInTheDocument();
  await waitFor(() => expect(feedback.success).toHaveBeenCalledWith("Checked out successfully."), {
    timeout: 3000,
  });
  expect(calls).toBe(2);
});

test("reports temporarily unavailable face verification and supports closing the result", async () => {
  server.use(
    http.post(`${API_BASE_URL}/attendance/kiosk/check-in/`, () =>
      HttpResponse.json(
        { error: "Liveness check is temporarily unavailable. Try again." },
        { status: 503 },
      ),
    ),
  );
  const user = userEvent.setup();
  renderKiosk();
  await user.click(screen.getByRole("button", { name: "Check In" }));
  await user.click(screen.getByRole("button", { name: "Capture & Verify" }));
  const result = screen.getByRole("region", { name: "Attendance result" });
  expect(
    within(result).getByRole("heading", { name: "Verification unavailable" }),
  ).toBeInTheDocument();
  expect(within(result).getByText(/temporarily unavailable/)).toBeInTheDocument();
  await user.click(within(result).getByRole("button", { name: "Close result" }));
  expect(screen.getByRole("button", { name: "Capture & Verify" })).toBeInTheDocument();
});

test("does not call attendance APIs until an action is selected and cancels the capture", async () => {
  let requests = 0;
  server.use(
    http.post(`${API_BASE_URL}/attendance/kiosk/check-in/`, () => {
      requests += 1;
      return HttpResponse.json({ ok: true });
    }),
  );
  const user = userEvent.setup();
  renderKiosk();
  await user.click(screen.getByRole("button", { name: "Capture & Verify" }));
  expect(requests).toBe(0);
  await user.click(screen.getByRole("button", { name: "Check In" }));
  await user.click(screen.getByRole("button", { name: "Cancel capture" }));
  expect(screen.getByRole("button", { name: "Check In" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Capture & Verify" }));
  expect(requests).toBe(0);
});
