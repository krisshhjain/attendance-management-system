import { afterEach, test, expect, vi } from "vitest";
import { getCurrentCoordinates } from "../src/lib/location.js";

afterEach(() => vi.restoreAllMocks());

test("returns coordinates and requests precise, fresh location data", async () => {
  const getCurrentPosition = vi.fn((success) =>
    success({ coords: { latitude: 1, longitude: 2, accuracy: 3 } }),
  );
  vi.stubGlobal("navigator", { geolocation: { getCurrentPosition } });

  await expect(getCurrentCoordinates()).resolves.toEqual({
    latitude: 1,
    longitude: 2,
    accuracy: 3,
  });
  expect(getCurrentPosition).toHaveBeenCalledWith(expect.any(Function), expect.any(Function), {
    enableHighAccuracy: true,
    timeout: 10000,
    maximumAge: 0,
  });
});

test.each([
  [1, "Location permission is required"],
  [2, "Location information is unavailable"],
  [3, "Location request timed out"],
  [9, "Unable to retrieve your location"],
])("maps geolocation error %i to actionable guidance", async (code, message) => {
  vi.stubGlobal("navigator", {
    geolocation: { getCurrentPosition: (_success, fail) => fail({ code }) },
  });

  await expect(getCurrentCoordinates()).rejects.toMatchObject({
    code,
    message: expect.stringContaining(message),
  });
});

test("rejects when geolocation is not available", async () => {
  vi.stubGlobal("navigator", {});
  await expect(getCurrentCoordinates()).rejects.toMatchObject({
    code: "NOT_SUPPORTED",
    message: expect.stringContaining("not supported"),
  });
});
