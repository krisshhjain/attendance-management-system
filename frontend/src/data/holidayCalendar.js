/**
 * data/holidayCalendar.js — Holiday data hooks for the Dailoqa AMS frontend.
 *
 * This module is the public entry point for holiday data. It:
 *  • Re-exports pure utility functions from holidayDateUtils.js so consumers
 *    only need to import from this single module.
 *  • Provides useActiveHolidays (all holidays from the backend) and
 *    useUpcomingHolidays (future active holidays, pre-sorted and colour-tagged).
 */
import { useQuery } from "@tanstack/react-query";
import { fetchActiveHolidays } from "../lib/api.js";
import { localDateKey } from "./holidayDateUtils.js";
export {
  classifyDate,
  formatHolidayDate,
  indexActiveHolidays,
  localDateKey,
} from "./holidayDateUtils.js";

/** Fetches all active holidays. Cached for 5 minutes (staleTime). */
export function useActiveHolidays() {
  return useQuery({
    queryKey: ["holidays", "active"],
    queryFn: fetchActiveHolidays,
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Returns upcoming (today or later) active holidays, sorted ascending by date.
 * The `color` field is added here for use by calendar UI components that expect
 * a colour property on each holiday event. All upcoming holidays share the same
 * indigo brand colour.
 */
export function useUpcomingHolidays() {
  const query = useActiveHolidays();
  const today = localDateKey();
  const holidays = (query.data ?? [])
    .filter((holiday) => holiday.is_active !== false && holiday.date >= today)
    .map((holiday) => ({ ...holiday, color: "#6366f1" }))
    .sort((a, b) => a.date.localeCompare(b.date));

  return { ...query, holidays };
}
