/**
 * lib/date.js — Display formatting utilities for dates, times, and durations.
 *
 * All functions return a dash (“—”) for missing/falsy input rather than
 * throwing, so they are safe to call on optional API fields.
 * Locale formatting uses `undefined` as the locale argument, which inherits
 * the browser's default locale — the output is not guaranteed to be consistent
 * across environments.
 */

/**
 * Formats an ISO date-time string or Date-constructible value as a locale time
 * string (e.g. "09:30 AM").
 */
export function formatTime(value) {
  if (!value) return "—";
  const date = parse(value);
  if (!date) return "—";
  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
}

export function formatDate(value) {
  if (!value) return "—";
  const date = parse(value);
  if (!date) return String(value);
  return date.toLocaleDateString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

/**
 * Formats a duration value from the backend into a human-readable "Xh Ym" string.
 *
 * The backend may return durations in three different formats:
 *  1. HH:MM:SS[.ffffff] (Django DurationField default for < 1 day)
 *  2. "N day(s), HH:MM:SS[.ffffff]" (Django DurationField when ≥ 1 day)
 *  3. A plain numeric string representing total seconds (legacy format)
 * All three are handled; any unrecognised format returns "—".
 */
export function formatDuration(value) {
  if (!value) return "—";

  if (typeof value === "string") {
    const hms = /^(\d+):(\d{2}):(\d{2})(?:\.\d+)?$/.exec(value);

    if (hms) {
      const hours = Number(hms[1]);
      const minutes = Number(hms[2]);
      return `${hours}h ${minutes}m`;
    }

    const djangoDuration = /^(?:(\d+)\s+days?,\s*)?(\d{1,2}):(\d{2}):(\d{2})(?:\.\d+)?$/.exec(
      value,
    );

    if (djangoDuration) {
      const days = Number(djangoDuration[1] || 0);
      const hours = days * 24 + Number(djangoDuration[2]);
      const minutes = Number(djangoDuration[3]);
      return `${hours}h ${minutes}m`;
    }

    const seconds = Number(value);

    if (Number.isFinite(seconds)) {
      const totalMinutes = Math.floor(seconds / 60);
      const hours = Math.floor(totalMinutes / 60);
      const minutes = totalMinutes % 60;

      return `${hours}h ${minutes}m`;
    }
  }

  return "—";
}

/**
 * Returns a time-of-day greeting string based on the local hour.
 * Boundaries: morning < 12, afternoon 12–16, evening ≥ 17.
 */
export function greeting(date = new Date()) {
  const hour = date.getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

function parse(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}
