import assert from "node:assert/strict";
import test from "node:test";
import { classifyDate, formatHolidayDate, indexActiveHolidays, localDateKey } from "../src/data/holidayDateUtils.js";

test("active holiday records are indexed by exact date and inactive records are ignored", () => {
  const holidayByDate = indexActiveHolidays([
    { date: "2026-01-26", name: "Republic Day", is_active: true },
    { date: "2026-01-27", name: "Old Holiday", is_active: false },
  ]);

  assert.equal(holidayByDate.get("2026-01-26").name, "Republic Day");
  assert.equal(holidayByDate.has("2026-01-27"), false);
});

test("weekday holiday and weekend holiday retain distinct date classifications", () => {
  const holidayByDate = indexActiveHolidays([
    { date: "2026-01-26", name: "Republic Day", is_active: true },
    { date: "2026-01-31", name: "Weekend Event", is_active: true },
  ]);

  const weekdayHoliday = classifyDate("2026-01-26", holidayByDate, false);
  assert.deepEqual(weekdayHoliday, { status: "HOLIDAY", holidayName: "Republic Day" });
  assert.notEqual(weekdayHoliday.status, "ABSENT");
  assert.notEqual(weekdayHoliday.status, "YET_TO_CHECK_IN");
  assert.deepEqual(classifyDate("2026-01-31", holidayByDate, true), { status: "WEEKEND", holidayName: "Weekend Event" });
  assert.deepEqual(classifyDate("2026-01-27", holidayByDate, false), { status: null, holidayName: null });
});

test("date-only holiday formatting does not shift the calendar date across timezone boundaries", () => {
  const originalTimezone = process.env.TZ;
  process.env.TZ = "Pacific/Honolulu";
  try {
    assert.equal(formatHolidayDate("2026-01-01", { year: "numeric", month: "2-digit", day: "2-digit" }), "01/01/2026");
    assert.equal(localDateKey(new Date(2026, 0, 1, 0, 5)), "2026-01-01");
  } finally {
    if (originalTimezone === undefined) delete process.env.TZ;
    else process.env.TZ = originalTimezone;
  }
});
