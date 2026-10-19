/**
 * Produces a locale-independent date key in YYYY-MM-DD format from a Date object.
 * Used as the canonical key for holiday lookups; avoids timezone shifting that
 * `new Date().toISOString()` would introduce for users east of UTC.
 */
export function localDateKey(date = new Date()) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

/**
 * Builds a Map from date string (YYYY-MM-DD) to holiday object for O(1) lookups.
 * Inactive holidays (is_active === false) are excluded from the index.
 */
export function indexActiveHolidays(holidays) {
  return new Map(
    (holidays ?? [])
      .filter((holiday) => holiday.is_active !== false)
      .map((holiday) => [holiday.date, holiday]),
  );
}

/**
 * Classifies a single date as WEEKEND, HOLIDAY, or null (normal working day).
 *
 * @param {string} dateKey - YYYY-MM-DD key for the date to classify.
 * @param {Map<string, object>} holidayByDate - Index built by indexActiveHolidays.
 * @param {boolean} isWeekend - True if the date falls on a weekend.
 * @returns {{ status: "WEEKEND"|"HOLIDAY"|null, holidayName: string|null }}
 */
export function classifyDate(dateKey, holidayByDate, isWeekend) {
  const holiday = holidayByDate.get(dateKey);
  return {
    status: isWeekend ? "WEEKEND" : holiday ? "HOLIDAY" : null,
    holidayName: holiday?.name ?? null,
  };
}

const DEFAULT_HOLIDAY_DATE_OPTIONS = Object.freeze({
  day: "2-digit",
  month: "short",
  year: "numeric",
});

/**
 * Formats a YYYY-MM-DD date string for display using Intl.DateTimeFormat.
 *
 * The date string is split and reconstructed using `new Date(year, month-1, day)`
 * rather than `new Date(dateString)` to avoid the UTC-midnight issue where ISO
 * strings are parsed as UTC and then displayed a day earlier in negative-offset
 * timezones.
 */
export function formatHolidayDate(dateValue, options) {
  const [year, month, day] = dateValue.split("-").map(Number);
  return new Intl.DateTimeFormat(undefined, options ?? DEFAULT_HOLIDAY_DATE_OPTIONS).format(
    new Date(year, month - 1, day),
  );
}
