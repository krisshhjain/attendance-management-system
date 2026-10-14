import { test, expect } from "vitest";
import { formatDate, formatDuration, formatTime, greeting } from "../src/lib/date.js";

test("formats supported attendance durations and rejects malformed values", () => {
  expect(formatDuration("08:05:59")).toBe("8h 5m");
  expect(formatDuration("2 days, 03:04:00")).toBe("51h 4m");
  expect(formatDuration("3665")).toBe("1h 1m");
  expect(formatDuration("not a duration")).toBe("—");
  expect(formatDuration(0)).toBe("—");
});

test("formats valid dates and returns a safe fallback for invalid dates", () => {
  expect(formatDate(null)).toBe("—");
  expect(formatDate("not-a-date")).toBe("not-a-date");

  const timestamp = "2026-01-26T13:05:00Z";
  const expectedLocalTime = new Date(timestamp).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
  expect(formatTime(timestamp)).toBe(expectedLocalTime);
  expect(formatTime("not-a-date")).toBe("—");
});

test("selects greetings at morning and evening boundaries", () => {
  expect(greeting(new Date(2026, 0, 1, 11, 59))).toBe("Good morning");
  expect(greeting(new Date(2026, 0, 1, 12, 0))).toBe("Good afternoon");
  expect(greeting(new Date(2026, 0, 1, 17, 0))).toBe("Good evening");
});
