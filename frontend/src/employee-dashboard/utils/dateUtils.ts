export const MONTH_NAMES_SHORT = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
];

export const MONTH_NAMES_FULL = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"
];

export const DAY_NAMES_SHORT = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
export const DAY_NAMES_FULL = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
export const WORK_DAYS_SHORT = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];

/**
 * Format a Date object to YYYY-MM-DD string
 */
export function formatToISODate(date: Date = new Date()): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

/**
 * Parse a YYYY-MM-DD string into a local Date object
 */
export function parseISODate(isoStr: string): Date {
  const [y, m, d] = isoStr.split("-").map(Number);
  return new Date(y, m - 1, d);
}

/**
 * Format a Date object to "DD MMM YYYY" (e.g. "25 Sep 2026")
 */
export function formatDateDisplay(date: Date | string): string {
  const d = typeof date === "string" ? parseISODate(date) : date;
  const day = String(d.getDate()).padStart(2, "0");
  const month = MONTH_NAMES_SHORT[d.getMonth()];
  const year = d.getFullYear();
  return `${day} ${month} ${year}`;
}

/**
 * Format Date to "Day, DD Month" (e.g. "Friday, 25 September")
 */
export function formatDateFullDisplay(date: Date = new Date()): string {
  const dayName = DAY_NAMES_FULL[date.getDay()];
  const day = date.getDate();
  const month = MONTH_NAMES_FULL[date.getMonth()];
  return `${dayName}, ${day} ${month}`;
}

/**
 * Format Date to Time string "hh:mm AM/PM" (e.g. "09:15 AM")
 */
export function formatTimeDisplay(date: Date = new Date()): string {
  let hours = date.getHours();
  const minutes = date.getMinutes();
  const ampm = hours >= 12 ? "PM" : "AM";
  hours = hours % 12;
  hours = hours ? hours : 12; // 0 hour should be 12
  const formattedMinutes = minutes < 10 ? `0${minutes}` : minutes;
  const formattedHours = hours < 10 ? `0${hours}` : hours;
  return `${formattedHours}:${formattedMinutes} ${ampm}`;
}

/**
 * Format Date to 24-hour time "HH:mm" (e.g. "09:15" or "17:45")
 */
export function formatTime24(date: Date = new Date()): string {
  const h = String(date.getHours()).padStart(2, "0");
  const m = String(date.getMinutes()).padStart(2, "0");
  return `${h}:${m}`;
}

/**
 * Parse any time string ("09:15 AM", "9:15 PM", "17:45", "09:15") into total minutes from midnight
 */
export function timeStringToMinutes(timeStr: string): number | null {
  if (!timeStr || timeStr === "--:--" || timeStr.trim() === "") return null;

  // 12-hour format with AM/PM
  const match12 = timeStr.match(/(\d{1,2}):(\d{2})\s*(AM|PM)/i);
  if (match12) {
    let hour = parseInt(match12[1], 10) % 12;
    if (match12[3].toUpperCase() === "PM") hour += 12;
    const minutes = parseInt(match12[2], 10);
    return hour * 60 + minutes;
  }

  // 24-hour format
  const match24 = timeStr.match(/(\d{1,2}):(\d{2})/);
  if (match24) {
    const hour = parseInt(match24[1], 10);
    const minutes = parseInt(match24[2], 10);
    return hour * 60 + minutes;
  }

  return null;
}

/**
 * Calculate working hours string and total minutes between checkIn and checkOut
 */
export function calculateWorkingHours(
  checkInStr: string,
  checkOutStr: string
): { formatted: string; minutes: number } {
  const inMins = timeStringToMinutes(checkInStr);
  const outMins = timeStringToMinutes(checkOutStr);

  if (inMins === null || outMins === null || outMins < inMins) {
    return { formatted: "--:--", minutes: 0 };
  }

  const diffMins = outMins - inMins;
  const hours = Math.floor(diffMins / 60);
  const mins = diffMins % 60;

  const formatted = `${String(hours).padStart(2, "0")}h ${String(mins).padStart(2, "0")}m`;
  return { formatted, minutes: diffMins };
}

/**
 * Calculate current working hours from checkIn up to right now
 */
export function calculateCurrentWorkingHours(checkInStr: string): { formatted: string; minutes: number } {
  const inMins = timeStringToMinutes(checkInStr);
  if (inMins === null) return { formatted: "00h 00m", minutes: 0 };

  const now = new Date();
  const currentMins = now.getHours() * 60 + now.getMinutes();
  const diffMins = Math.max(0, currentMins - inMins);

  const hours = Math.floor(diffMins / 60);
  const mins = diffMins % 60;
  return {
    formatted: `${String(hours).padStart(2, "0")}h ${String(mins).padStart(2, "0")}m`,
    minutes: diffMins,
  };
}

/**
 * Get greeting based on time of day
 */
export function getGreeting(userName?: string): string {
  const hour = new Date().getHours();
  let timeGreeting = "Good Morning";
  if (hour >= 12 && hour < 17) {
    timeGreeting = "Good Afternoon";
  } else if (hour >= 17) {
    timeGreeting = "Good Evening";
  }
  return userName ? `${timeGreeting}, ${userName}` : timeGreeting;
}

/**
 * Calculate timeline position percent (0% to 100%)
 * Timeline default window: 09:00 AM (540m) to 06:00 PM (1080m) = 540m range
 */
export function calculateTimelinePosition(timeStr: string): number {
  const minutes = timeStringToMinutes(timeStr);
  if (minutes === null) return 0;
  // Map between 09:00 (540) and 18:00 (1080)
  const pos = ((minutes - 540) / 540) * 100;
  return Math.max(0, Math.min(100, pos));
}

/**
 * Return dates for a week (Monday to Sunday) given a base date and week offset
 */
export function getWeekDates(baseDate: Date = new Date(), weekOffset = 0): Date[] {
  const d = new Date(baseDate);
  // Get current day of week: Sunday is 0, Monday is 1, ..., Saturday is 6
  const day = d.getDay();
  // We want Monday to be start of week: distance to Monday
  const diffToMonday = day === 0 ? -6 : 1 - day;
  d.setDate(d.getDate() + diffToMonday + weekOffset * 7);

  const week: Date[] = [];
  for (let i = 0; i < 7; i++) {
    const dayDate = new Date(d);
    dayDate.setDate(d.getDate() + i);
    week.push(dayDate);
  }
  return week;
}

/**
 * Check if a date is Today
 */
export function isToday(date: Date | string): boolean {
  const today = formatToISODate(new Date());
  const check = typeof date === "string" ? date : formatToISODate(date);
  return today === check;
}

/**
 * Check if a date is a weekend (Saturday or Sunday)
 */
export function isWeekend(date: Date | string): boolean {
  const d = typeof date === "string" ? parseISODate(date) : date;
  const day = d.getDay();
  return day === 0 || day === 6;
}

/**
 * Calculate working days between two ISO dates (inclusive), excluding weekends
 */
export function countWorkingDays(startDateStr: string, endDateStr: string): number {
  if (!startDateStr || !endDateStr) return 1;
  const start = parseISODate(startDateStr);
  const end = parseISODate(endDateStr);

  if (start > end) return 0;

  let count = 0;
  const cur = new Date(start);
  while (cur <= end) {
    if (!isWeekend(cur)) {
      count++;
    }
    cur.setDate(cur.getDate() + 1);
  }
  return Math.max(1, count);
}

/**
 * Relative time string from ISO string or timestamp
 */
export function getRelativeTimeString(dateInput: string | Date | number): string {
  const d = typeof dateInput === "string" ? new Date(dateInput) : new Date(dateInput);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffMin < 1) return "Just now";
  if (diffMin < 60) return `${diffMin} min ago`;
  if (diffHour === 1) return "1 hr ago";
  if (diffHour < 24) return `${diffHour} hrs ago`;
  if (diffDay === 1) return "Yesterday";
  if (diffDay < 7) return `${diffDay} days ago`;
  return formatDateDisplay(d);
}
