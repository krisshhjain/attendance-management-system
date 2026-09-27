import type {
  AttendanceRecord,
  Holiday,
  LeaveBalance,
  LeaveRequest,
  NotificationItem,
  OnDutyRequest,
  RegularizationRequest,
  UserProfile,
  UserSettings,
} from "../types";
import {
  calculateWorkingHours,
  formatDateDisplay,
  formatTimeDisplay,
  formatToISODate,
  getRelativeTimeString,
  isWeekend,
  MONTH_NAMES_SHORT,
} from "../utils/dateUtils";

const STORAGE_KEYS = {
  USER: "attendpro_user_profile_v4",
  ATTENDANCE: "attendpro_attendance_records_v4",
  LEAVE_REQUESTS: "attendpro_leave_requests_v4",
  LEAVE_BALANCES: "attendpro_leave_balances_v4",
  REGULARIZATIONS: "attendpro_regularizations_v4",
  ONDUTY: "attendpro_onduty_v4",
  HOLIDAYS: "attendpro_holidays_v4",
  NOTIFICATIONS: "attendpro_notifications_v4",
  SETTINGS: "attendpro_settings_v4",
  INITIALIZED_VERSION: "attendpro_seed_v4",
};

function safeJsonParse<T>(key: string, fallback: T): T {
  try {
    if (typeof window === "undefined" || !window.localStorage) return fallback;
    const data = window.localStorage.getItem(key);
    if (!data) return fallback;
    const parsed = JSON.parse(data);
    return parsed !== null && parsed !== undefined ? (parsed as T) : fallback;
  } catch (err) {
    console.warn(`Error reading ${key} from localStorage, using fallback:`, err);
    return fallback;
  }
}

function safeJsonSet(key: string, value: unknown) {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      window.localStorage.setItem(key, JSON.stringify(value));
    }
  } catch (err) {
    console.warn(`Error saving ${key} to localStorage:`, err);
  }
}

/**
 * Seed data generation relative to the current real date
 */
function generateSeedData() {
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth(); // 0-11
  const currentDay = now.getDate();

  // User Profile
  const user: UserProfile = {
    id: "USR-1042",
    name: "Akansha Sharma",
    employeeId: "ATD-1042",
    email: "akansha.sharma@attendpro.demo",
    phone: "+91 98765 43210",
    department: "Product & Design",
    designation: "Product Designer",
    manager: "Rahul Mehta",
    joiningDate: `12 March ${currentYear - 2}`,
    location: "Gurugram Office",
  };

  // Holidays for current year
  const holidays: Holiday[] = [
    { id: "HOL-1", name: "New Year's Day", date: `${currentYear}-01-01`, type: "Gazetted" },
    { id: "HOL-2", name: "Republic Day", date: `${currentYear}-01-26`, type: "Gazetted" },
    { id: "HOL-3", name: "Holi", date: `${currentYear}-03-25`, type: "Gazetted" },
    { id: "HOL-4", name: "Good Friday", date: `${currentYear}-04-03`, type: "Restricted" },
    { id: "HOL-5", name: "Eid-ul-Fitr", date: `${currentYear}-04-11`, type: "Gazetted" },
    { id: "HOL-6", name: "Independence Day", date: `${currentYear}-08-15`, type: "Gazetted" },
    { id: "HOL-7", name: "Gandhi Jayanti", date: `${currentYear}-10-02`, type: "Gazetted" },
    { id: "HOL-8", name: "Dussehra", date: `${currentYear}-10-20`, type: "Gazetted" },
    { id: "HOL-9", name: "Diwali", date: `${currentYear}-11-08`, type: "Gazetted" },
    { id: "HOL-10", name: "Christmas", date: `${currentYear}-12-25`, type: "Gazetted" },
  ];

  // Generate Attendance Records for 90 days (past 60 days, current month, next 30 days)
  const attendanceRecords: Record<string, AttendanceRecord> = {};

  const startDate = new Date(currentYear, currentMonth - 2, 1);
  const endDate = new Date(currentYear, currentMonth + 1, 0);

  const loopDate = new Date(startDate);
  while (loopDate <= endDate) {
    const iso = formatToISODate(loopDate);
    const dayOfWeek = loopDate.getDay();
    const isPast = loopDate < new Date(currentYear, currentMonth, currentDay);
    const isCurrentDay =
      loopDate.getDate() === currentDay &&
      loopDate.getMonth() === currentMonth &&
      loopDate.getFullYear() === currentYear;

    if (dayOfWeek === 0 || dayOfWeek === 6) {
      // Weekend
      attendanceRecords[iso] = {
        id: `att-${iso}`,
        date: iso,
        status: "Weekend",
        checkIn: "--:--",
        checkOut: "--:--",
        workingHours: "00h 00m",
        workingMinutes: 0,
        attendanceType: "Office",
      };
    } else if (isCurrentDay) {
      // Today: Initially awaiting check-in
      attendanceRecords[iso] = {
        id: `att-${iso}`,
        date: iso,
        status: "Pending",
        checkIn: "--:--",
        checkOut: "--:--",
        workingHours: "00h 00m",
        workingMinutes: 0,
        attendanceType: "Office",
        notes: "Today's attendance record",
      };
    } else if (isPast) {
      // Deterministic realistic pattern for past weekdays
      const dayNum = loopDate.getDate();
      if (dayNum % 13 === 0) {
        // On Leave
        attendanceRecords[iso] = {
          id: `att-${iso}`,
          date: iso,
          status: "On Leave",
          checkIn: "--:--",
          checkOut: "--:--",
          workingHours: "00h 00m",
          workingMinutes: 0,
          attendanceType: "Office",
          notes: "Casual Leave",
        };
      } else if (dayNum % 9 === 0) {
        // Work From Home
        const inTime = "09:15 AM";
        const outTime = "05:30 PM";
        const { formatted, minutes } = calculateWorkingHours(inTime, outTime);
        attendanceRecords[iso] = {
          id: `att-${iso}`,
          date: iso,
          status: "Work From Home",
          checkIn: inTime,
          checkOut: outTime,
          workingHours: formatted,
          workingMinutes: minutes,
          attendanceType: "Work From Home",
        };
      } else if (dayNum % 17 === 0) {
        // On Duty
        const inTime = "09:00 AM";
        const outTime = "06:00 PM";
        const { formatted, minutes } = calculateWorkingHours(inTime, outTime);
        attendanceRecords[iso] = {
          id: `att-${iso}`,
          date: iso,
          status: "On Duty",
          checkIn: inTime,
          checkOut: outTime,
          workingHours: formatted,
          workingMinutes: minutes,
          attendanceType: "On Duty",
          location: "Client Office",
        };
      } else if (dayNum === 24 && loopDate.getMonth() === currentMonth) {
        // A recent day with Missing Check-out for regularization showcase
        attendanceRecords[iso] = {
          id: `att-${iso}`,
          date: iso,
          status: "Missing Check-out",
          checkIn: "09:14 AM",
          checkOut: "--:--",
          workingHours: "07h --m",
          workingMinutes: 420,
          attendanceType: "Office",
          notes: "Missing checkout recorded",
        };
      } else {
        // Present
        const minsOffset = (dayNum * 7) % 30; // 0..29 min variation
        const inMin = 10 + (minsOffset % 15);
        const inTime = `09:${String(inMin).padStart(2, "0")} AM`;
        const outMin = 30 + (minsOffset % 25);
        const outTime = `05:${String(outMin).padStart(2, "0")} PM`;
        const { formatted, minutes } = calculateWorkingHours(inTime, outTime);

        attendanceRecords[iso] = {
          id: `att-${iso}`,
          date: iso,
          status: "Present",
          checkIn: inTime,
          checkOut: outTime,
          workingHours: formatted,
          workingMinutes: minutes,
          attendanceType: "Office",
        };
      }
    } else {
      // Future day
      attendanceRecords[iso] = {
        id: `att-${iso}`,
        date: iso,
        status: "Pending",
        checkIn: "--:--",
        checkOut: "--:--",
        workingHours: "00h 00m",
        workingMinutes: 0,
        attendanceType: "Office",
      };
    }

    loopDate.setDate(loopDate.getDate() + 1);
  }

  // Leave Balances
  const leaveBalances: LeaveBalance[] = [
    { type: "Casual Leave", total: 12, used: 4, available: 8, pending: 1 },
    { type: "Sick Leave", total: 10, used: 3, available: 7, pending: 0 },
    { type: "Earned Leave", total: 15, used: 5, available: 10, pending: 0 },
    { type: "Compensatory Off", total: 3, used: 1, available: 2, pending: 0 },
  ];

  // Leave Requests
  const leaveRequests: LeaveRequest[] = [
    {
      id: `LR-${currentYear}-01`,
      leaveType: "Casual Leave",
      startDate: formatToISODate(new Date(currentYear, currentMonth, 14)),
      endDate: formatToISODate(new Date(currentYear, currentMonth, 15)),
      duration: 2,
      durationLabel: "2 days",
      reason: "Personal commitment",
      status: "Approved",
      appliedOn: formatToISODate(new Date(currentYear, currentMonth, 10)),
      reviewedBy: "Rahul Mehta",
      reviewedOn: formatToISODate(new Date(currentYear, currentMonth, 11)),
    },
    {
      id: `LR-${currentYear}-02`,
      leaveType: "Sick Leave",
      startDate: formatToISODate(new Date(currentYear, currentMonth - 1, 3)),
      endDate: formatToISODate(new Date(currentYear, currentMonth - 1, 3)),
      duration: 1,
      durationLabel: "1 day",
      reason: "Unwell with fever",
      status: "Approved",
      appliedOn: formatToISODate(new Date(currentYear, currentMonth - 1, 3)),
      reviewedBy: "Rahul Mehta",
    },
    {
      id: `LR-${currentYear}-03`,
      leaveType: "Casual Leave",
      startDate: formatToISODate(new Date(currentYear, currentMonth, Math.min(28, currentDay + 5))),
      endDate: formatToISODate(new Date(currentYear, currentMonth, Math.min(28, currentDay + 5))),
      duration: 1,
      durationLabel: "1 day",
      reason: "Family event",
      status: "Pending",
      appliedOn: formatToISODate(new Date(currentYear, currentMonth, currentDay)),
    },
    {
      id: `LR-${currentYear}-04`,
      leaveType: "Earned Leave",
      startDate: formatToISODate(new Date(currentYear, currentMonth - 1, 21)),
      endDate: formatToISODate(new Date(currentYear, currentMonth - 1, 21)),
      duration: 1,
      durationLabel: "1 day",
      reason: "Travel out of town",
      status: "Rejected",
      appliedOn: formatToISODate(new Date(currentYear, currentMonth - 1, 15)),
    },
  ];

  // Regularizations
  const regularizations: RegularizationRequest[] = [
    {
      id: `REG-${currentYear}-04`,
      periodType: "Day",
      date: formatDateDisplay(new Date(currentYear, currentMonth, Math.max(1, currentDay - 2))),
      startDate: formatToISODate(new Date(currentYear, currentMonth, Math.max(1, currentDay - 2))),
      checkIn: "09:15 AM",
      checkOut: "05:45 PM",
      totalHours: "08h 30m",
      reason: "Forgot to Check Out",
      description: "Left in a hurry for client discussion, forgot to tap check out.",
      status: "Approved",
      submittedOn: formatDateDisplay(new Date(currentYear, currentMonth, Math.max(1, currentDay - 1))),
    },
    {
      id: `REG-${currentYear}-03`,
      periodType: "Day",
      date: formatDateDisplay(new Date(currentYear, currentMonth, Math.max(1, currentDay - 7))),
      startDate: formatToISODate(new Date(currentYear, currentMonth, Math.max(1, currentDay - 7))),
      checkIn: "09:20 AM",
      checkOut: "05:30 PM",
      totalHours: "08h 10m",
      reason: "Device Issue",
      description: "Biometric kiosk was rebooting in morning.",
      status: "Pending",
      submittedOn: formatDateDisplay(new Date(currentYear, currentMonth, Math.max(1, currentDay - 6))),
    },
    {
      id: `REG-${currentYear}-02`,
      periodType: "Day",
      date: formatDateDisplay(new Date(currentYear, currentMonth - 1, 8)),
      startDate: formatToISODate(new Date(currentYear, currentMonth - 1, 8)),
      checkIn: "09:10 AM",
      checkOut: "06:00 PM",
      totalHours: "08h 50m",
      reason: "Incorrect Attendance",
      description: "Logged attendance under incorrect location.",
      status: "Rejected",
      submittedOn: formatDateDisplay(new Date(currentYear, currentMonth - 1, 9)),
    },
  ];

  // On Duty Requests
  const onDutyRequests: OnDutyRequest[] = [
    {
      id: `OD-${currentYear}-03`,
      date: formatDateDisplay(new Date(currentYear, currentMonth, Math.min(28, currentDay + 3))),
      startDate: formatToISODate(new Date(currentYear, currentMonth, Math.min(28, currentDay + 3))),
      startTime: "09:00 AM",
      endTime: "05:00 PM",
      location: "Client office, Cyber City",
      purpose: "UX Research Sprint",
      description: "Onsite user testing with enterprise clients",
      status: "Pending",
      submittedOn: formatDateDisplay(new Date(currentYear, currentMonth, currentDay)),
    },
    {
      id: `OD-${currentYear}-02`,
      date: formatDateDisplay(new Date(currentYear, currentMonth, Math.max(1, currentDay - 10))),
      startDate: formatToISODate(new Date(currentYear, currentMonth, Math.max(1, currentDay - 10))),
      startTime: "10:00 AM",
      endTime: "04:30 PM",
      location: "Design Workshop Hub",
      purpose: "Design system alignment session",
      description: "Cross-functional design sprint with mobile team",
      status: "Approved",
      submittedOn: formatDateDisplay(new Date(currentYear, currentMonth, Math.max(1, currentDay - 11))),
    },
    {
      id: `OD-${currentYear}-01`,
      date: formatDateDisplay(new Date(currentYear, currentMonth - 1, 28)),
      startDate: formatToISODate(new Date(currentYear, currentMonth - 1, 28)),
      startTime: "09:30 AM",
      endTime: "02:00 PM",
      location: "Vendor site",
      purpose: "Vendor review",
      description: "Procurement hardware check",
      status: "Rejected",
      submittedOn: formatDateDisplay(new Date(currentYear, currentMonth - 1, 27)),
    },
  ];

  // Notifications
  const notifications: NotificationItem[] = [
    {
      id: "notif-1",
      title: "Attendance regularization approved",
      message: `Your regularization request for ${formatDateDisplay(new Date(currentYear, currentMonth, Math.max(1, currentDay - 2)))} has been approved.`,
      timestamp: new Date(now.getTime() - 10 * 60 * 1000).toISOString(),
      timeAgo: "10 min ago",
      icon: "check",
      unread: true,
      link: "regularization",
    },
    {
      id: "notif-2",
      title: "Missing check-out alert",
      message: "You haven't checked out for today's shift yet.",
      timestamp: new Date(now.getTime() - 60 * 60 * 1000).toISOString(),
      timeAgo: "1 hr ago",
      icon: "clock",
      unread: true,
      link: "dashboard",
    },
    {
      id: "notif-3",
      title: "Leave request approved",
      message: `Your leave request for 14–15 ${MONTH_NAMES_SHORT[currentMonth]} has been approved by manager.`,
      timestamp: new Date(now.getTime() - 24 * 60 * 60 * 1000).toISOString(),
      timeAgo: "Yesterday",
      icon: "leave",
      unread: true,
      link: "leave",
    },
    {
      id: "notif-4",
      title: "Face verification enabled",
      message: "Biometric kiosk check-in is active for your account.",
      timestamp: new Date(now.getTime() - 48 * 60 * 60 * 1000).toISOString(),
      timeAgo: "2 days ago",
      icon: "camera",
      unread: false,
      link: "attendance",
    },
    {
      id: "notif-5",
      title: "On Duty request submitted",
      message: "Your request for client site visit is awaiting manager approval.",
      timestamp: new Date(now.getTime() - 72 * 60 * 60 * 1000).toISOString(),
      timeAgo: "3 days ago",
      icon: "briefcase",
      unread: false,
      link: "onduty",
    },
  ];

  // Settings
  const settings: UserSettings = {
    emailNotifications: true,
    pushNotifications: true,
    attendanceReminders: false,
    theme: (window.localStorage.getItem("attendpro-theme") as "light" | "dark") || "light",
    language: "English",
    timezone: "India Standard Time",
  };

  return {
    user,
    attendanceRecords,
    leaveBalances,
    leaveRequests,
    regularizations,
    onDutyRequests,
    holidays,
    notifications,
    settings,
  };
}

export const StorageService = {
  initialize() {
    try {
      const initialized = safeJsonParse<string | null>(STORAGE_KEYS.INITIALIZED_VERSION, null);
      if (!initialized || initialized !== "v4") {
        this.resetAllData();
      }
    } catch {
      this.resetAllData();
    }
  },

  resetAllData() {
    try {
      const seed = generateSeedData();
      safeJsonSet(STORAGE_KEYS.USER, seed.user);
      safeJsonSet(STORAGE_KEYS.ATTENDANCE, seed.attendanceRecords);
      safeJsonSet(STORAGE_KEYS.LEAVE_BALANCES, seed.leaveBalances);
      safeJsonSet(STORAGE_KEYS.LEAVE_REQUESTS, seed.leaveRequests);
      safeJsonSet(STORAGE_KEYS.REGULARIZATIONS, seed.regularizations);
      safeJsonSet(STORAGE_KEYS.ONDUTY, seed.onDutyRequests);
      safeJsonSet(STORAGE_KEYS.HOLIDAYS, seed.holidays);
      safeJsonSet(STORAGE_KEYS.NOTIFICATIONS, seed.notifications);
      safeJsonSet(STORAGE_KEYS.SETTINGS, seed.settings);
      safeJsonSet(STORAGE_KEYS.INITIALIZED_VERSION, "v4");
    } catch (err) {
      console.warn("Error during resetAllData:", err);
    }
  },

  getUser(): UserProfile {
    const seed = generateSeedData().user;
    return safeJsonParse<UserProfile>(STORAGE_KEYS.USER, seed) || seed;
  },

  saveUser(user: UserProfile) {
    safeJsonSet(STORAGE_KEYS.USER, user);
  },

  getAttendanceRecords(): Record<string, AttendanceRecord> {
    const seed = generateSeedData().attendanceRecords;
    const records = safeJsonParse<Record<string, AttendanceRecord>>(STORAGE_KEYS.ATTENDANCE, seed);
    return records && typeof records === "object" ? records : seed;
  },

  saveAttendanceRecords(records: Record<string, AttendanceRecord>) {
    safeJsonSet(STORAGE_KEYS.ATTENDANCE, records);
  },

  getLeaveBalances(): LeaveBalance[] {
    const seed = generateSeedData().leaveBalances;
    const data = safeJsonParse<LeaveBalance[]>(STORAGE_KEYS.LEAVE_BALANCES, seed);
    return Array.isArray(data) ? data : seed;
  },

  saveLeaveBalances(balances: LeaveBalance[]) {
    safeJsonSet(STORAGE_KEYS.LEAVE_BALANCES, balances);
  },

  getLeaveRequests(): LeaveRequest[] {
    const seed = generateSeedData().leaveRequests;
    const data = safeJsonParse<LeaveRequest[]>(STORAGE_KEYS.LEAVE_REQUESTS, seed);
    return Array.isArray(data) ? data : seed;
  },

  saveLeaveRequests(requests: LeaveRequest[]) {
    safeJsonSet(STORAGE_KEYS.LEAVE_REQUESTS, requests);
  },

  getRegularizations(): RegularizationRequest[] {
    const seed = generateSeedData().regularizations;
    const data = safeJsonParse<RegularizationRequest[]>(STORAGE_KEYS.REGULARIZATIONS, seed);
    return Array.isArray(data) ? data : seed;
  },

  saveRegularizations(requests: RegularizationRequest[]) {
    safeJsonSet(STORAGE_KEYS.REGULARIZATIONS, requests);
  },

  getOnDutyRequests(): OnDutyRequest[] {
    const seed = generateSeedData().onDutyRequests;
    const data = safeJsonParse<OnDutyRequest[]>(STORAGE_KEYS.ONDUTY, seed);
    return Array.isArray(data) ? data : seed;
  },

  saveOnDutyRequests(requests: OnDutyRequest[]) {
    safeJsonSet(STORAGE_KEYS.ONDUTY, requests);
  },

  getHolidays(): Holiday[] {
    const seed = generateSeedData().holidays;
    const data = safeJsonParse<Holiday[]>(STORAGE_KEYS.HOLIDAYS, seed);
    return Array.isArray(data) ? data : seed;
  },

  saveHolidays(holidays: Holiday[]) {
    safeJsonSet(STORAGE_KEYS.HOLIDAYS, holidays);
  },

  getNotifications(): NotificationItem[] {
    const seed = generateSeedData().notifications;
    const data = safeJsonParse<NotificationItem[]>(STORAGE_KEYS.NOTIFICATIONS, seed);
    return Array.isArray(data) ? data : seed;
  },

  saveNotifications(notifications: NotificationItem[]) {
    safeJsonSet(STORAGE_KEYS.NOTIFICATIONS, notifications);
  },

  getSettings(): UserSettings {
    const seed = generateSeedData().settings;
    return safeJsonParse<UserSettings>(STORAGE_KEYS.SETTINGS, seed) || seed;
  },

  saveSettings(settings: UserSettings) {
    safeJsonSet(STORAGE_KEYS.SETTINGS, settings);
  },
};
