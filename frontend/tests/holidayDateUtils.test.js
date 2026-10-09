import assert from "node:assert/strict";
import test from "node:test";
import { formatHolidayDate, indexActiveHolidays } from "../src/data/holidayDateUtils.js";

test("holiday date formatting supports defaults and caller options", () => {
  assert.match(formatHolidayDate("2026-01-26"), /2026/);
  const customFormat = formatHolidayDate("2026-01-26", { month: "long", day: "numeric", year: "numeric" });
  assert.match(customFormat, /January/);
  assert.match(customFormat, /26/);
  assert.match(customFormat, /2026/);
});

test("holiday indexing treats an omitted list as empty", () => {
  assert.equal(indexActiveHolidays().size, 0);
});
