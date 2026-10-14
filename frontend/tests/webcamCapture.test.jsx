import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { forwardRef, useImperativeHandle } from "react";
import { afterEach, expect, test, vi } from "vitest";
import WebcamCapture from "../src/components/WebcamCapture.jsx";

vi.mock("react-webcam", () => ({
  default: forwardRef(function MockWebcam(_props, ref) {
    useImperativeHandle(ref, () => ({ getScreenshot: () => "data:image/jpeg;base64,face" }));
    return <div data-testid="camera-feed" />;
  }),
}));

afterEach(() => vi.useRealTimers());

test("captures a single enrollment sample and supports cancellation", async () => {
  const onCapture = vi.fn();
  const onCancel = vi.fn();
  const user = userEvent.setup();
  render(<WebcamCapture onCapture={onCapture} onCancel={onCancel} />);

  expect(screen.getByText("Position face clearly within the frame.")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Capture & Verify" }));
  expect(onCapture).toHaveBeenCalledWith(["data:image/jpeg;base64,face"]);
  await user.click(screen.getByRole("button", { name: "Cancel" }));
  expect(onCancel).toHaveBeenCalledOnce();
});

test("captures exactly three burst samples and blocks another action while busy", async () => {
  vi.useFakeTimers();
  const onCapture = vi.fn();
  render(<WebcamCapture mode="burst" onCapture={onCapture} />);

  fireEvent.click(screen.getByRole("button", { name: "Start Capture" }));
  await act(async () => {
    await vi.advanceTimersByTimeAsync(3000);
  });

  expect(onCapture).toHaveBeenCalledWith([
    "data:image/jpeg;base64,face",
    "data:image/jpeg;base64,face",
    "data:image/jpeg;base64,face",
  ]);
});
