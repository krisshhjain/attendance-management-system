export function localDateKey(date = new Date()) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function indexActiveHolidays(holidays) {
  return new Map((holidays ?? []).filter((holiday) => holiday.is_active !== false).map((holiday) => [holiday.date, holiday]));
}

export function classifyDate(dateKey, holidayByDate, isWeekend) {
  const holiday = holidayByDate.get(dateKey);
  return { status: isWeekend ? "WEEKEND" : holiday ? "HOLIDAY" : null, holidayName: holiday?.name ?? null };
}

const DEFAULT_HOLIDAY_DATE_OPTIONS = Object.freeze({
  day: "2-digit",
  month: "short",
  year: "numeric",
});

export function formatHolidayDate(dateValue, options) {
  const [year, month, day] = dateValue.split("-").map(Number);
  return new Intl.DateTimeFormat(undefined, options ?? DEFAULT_HOLIDAY_DATE_OPTIONS)
    .format(new Date(year, month - 1, day));
}
