import assert from "node:assert/strict";
import test from "node:test";
import { createNotification, enqueueNotification, removeNotification } from "../src/feedback/feedbackState.js";
import { getErrorMessage } from "../src/feedback/errorMessage.js";

test("queues multiple notifications and prevents duplicates", () => {
  const first = createNotification({ severity: "success", message: "Saved." }, "one");
  const duplicate = createNotification({ severity: "success", message: "Saved." }, "two");
  const second = createNotification({ severity: "error", message: "Failed." }, "three");

  let state = enqueueNotification([], first);
  state = enqueueNotification(state, duplicate);
  state = enqueueNotification(state, second);

  assert.deepEqual(state.map((item) => item.id), ["one", "three"]);
});

test("notification duration is configured for auto-dismiss", () => {
  const notification = createNotification({ severity: "warning", message: "Check this.", duration: 1200 }, "one");
  assert.equal(notification.duration, 1200);
  assert.equal(createNotification({ message: "Persistent", duration: 0 }, "two").duration, 0);
});

test("manual close removes only the selected notification", () => {
  const first = createNotification({ message: "First" }, "one");
  const second = createNotification({ message: "Second" }, "two");
  assert.deepEqual(removeNotification([first, second], "one").map((item) => item.id), ["two"]);
});

test("normalizes safe API errors and hides unsafe details", () => {
  assert.equal(getErrorMessage({ message: "Email is already registered", status: 400 }), "Email is already registered");
  assert.equal(getErrorMessage({ status: 401 }), "Your session has expired. Please sign in again.");
  assert.equal(getErrorMessage({ message: "<html>secret</html>" }), "Something went wrong. Please try again.");
  assert.equal(getErrorMessage({ message: "Bearer token: abc" }), "Something went wrong. Please try again.");
});

test("unsafe error message checks remain safe on very long input", () => {
  const longMessage = "<".repeat(30000);
  const started = performance.now();
  assert.equal(getErrorMessage({ message: longMessage }), "Something went wrong. Please try again.");
  assert.ok(performance.now() - started < 1000);
});
