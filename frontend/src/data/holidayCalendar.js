import { useQuery } from "@tanstack/react-query";
import { fetchActiveHolidays } from "../lib/api.js";
import { localDateKey } from "./holidayDateUtils.js";
export { classifyDate, formatHolidayDate, indexActiveHolidays, localDateKey } from "./holidayDateUtils.js";

export function useActiveHolidays() {
  return useQuery({ queryKey: ["holidays", "active"], queryFn: fetchActiveHolidays, staleTime: 5 * 60 * 1000 });
}

export function useUpcomingHolidays() {
  const query = useActiveHolidays();
  const today = localDateKey();
  const holidays = (query.data ?? [])
    .filter((holiday) => holiday.is_active !== false && holiday.date >= today)
    .map((holiday) => ({ ...holiday, color: "#6366f1" }))
    .sort((a, b) => a.date.localeCompare(b.date));

  return { ...query, holidays };
}
