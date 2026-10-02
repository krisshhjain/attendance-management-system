// Shared company holiday calendar used by both employee and Super Admin dashboards.
export const COMPANY_HOLIDAYS = [
  { name: "New Year", date: "01-01-2026", color: "#ec4899" },
  { name: "Republic Day", date: "26-01-2026", color: "#3b82f6" },
  { name: "Holi", date: "04-03-2026", color: "#8b5cf6" },
  { name: "Eid-Ul-fitr", date: "20-03-2026", color: "#10b981" },
  { name: "Good Friday", date: "03-04-2026", color: "#f59e0b" },
  { name: "Gandhi Jayanti", date: "02-10-2026", color: "#6366f1" },
  { name: "Dussehra", date: "20-10-2026", color: "#ef4444" },
  { name: "Govardhan Puja", date: "09-11-2026", color: "#14b8a6" },
  { name: "Christmas", date: "25-12-2026", color: "#22c55e" },
];

export function getUpcomingHolidays(today = new Date()) {
  const startOfToday = new Date(today);
  startOfToday.setHours(0, 0, 0, 0);

  return COMPANY_HOLIDAYS
    .map((holiday) => {
      const [day, month, year] = holiday.date.split("-").map(Number);
      return { ...holiday, parsedDate: new Date(year, month - 1, day) };
    })
    .filter((holiday) => holiday.parsedDate >= startOfToday)
    .sort((a, b) => a.parsedDate - b.parsedDate);
}
