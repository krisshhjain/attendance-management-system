import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type {
  AttendanceActionState,
  AttendanceRecord,
  Holiday,
  LeaveBalance,
  LeaveRequest,
  NotificationItem,
  OnDutyRequest,
  Page,
  RegularizationRequest,
  UserProfile,
  UserSettings,
} from "../types";
import { formatToISODate } from "../utils/dateUtils";
import { ApiService } from "../services/apiService";

interface AppContextType {
  // State
  user: UserProfile;
  attendanceRecords: Record<string, AttendanceRecord>;
  leaveBalances: LeaveBalance[];
  leaveRequests: LeaveRequest[];
  regularizations: RegularizationRequest[];
  onDutyRequests: OnDutyRequest[];
  holidays: Holiday[];
  notifications: NotificationItem[];
  settings: UserSettings;
  unreadNotificationsCount: number;

  // Today specific computed
  todayRecord: AttendanceRecord;
  attendanceState: AttendanceActionState;

  // Navigation
  activePage: Page;
  setActivePage: (page: Page) => void;

  // UI state
  toast: string;
  showToast: (msg: string) => void;
  hideToast: () => void;
  isLoading: boolean;

  // Actions
  checkIn: (method?: "standard" | "face", location?: string) => Promise<void>;
  checkOut: (method?: "standard" | "face") => Promise<void>;
  applyLeave: (req: Omit<LeaveRequest, "id" | "appliedOn" | "status">) => Promise<void>;
  submitRegularization: (req: Omit<RegularizationRequest, "id" | "submittedOn" | "status">) => Promise<void>;
  submitOnDuty: (req: Omit<OnDutyRequest, "id" | "submittedOn" | "status">) => Promise<void>;
  markNotificationRead: (id: string) => Promise<void>;
  markAllNotificationsRead: () => Promise<void>;
  clearNotifications: () => Promise<void>;
  updateProfile: (profile: Partial<UserProfile>) => Promise<void>;
  updateSettings: (settings: Partial<UserSettings>) => Promise<void>;
  setTheme: (theme: "light" | "dark") => void;
  resetDemoData: () => Promise<void>;
  refreshAllData: () => Promise<void>;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

function getInitialPageFromHash(): Page {
  const hash = window.location.hash.replace("#", "").trim();
  const validPages: Page[] = [
    "dashboard",
    "attendance",
    "leave",
    "regularization",
    "onduty",
    "notifications",
    "profile",
    "settings",
  ];
  return validPages.includes(hash as Page) ? (hash as Page) : "dashboard";
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [activePage, setActivePageState] = useState<Page>(getInitialPageFromHash);
  const [isLoading, setIsLoading] = useState(true);
  const [toast, setToast] = useState("");

  // Initial state uses neutral empty defaults; real data loads from StorageService via refreshAllData on mount.
  const [user, setUser] = useState<UserProfile>({
    id: "",
    name: "",
    employeeId: "",
    email: "",
    phone: "",
    department: "",
    designation: "",
    manager: "",
    joiningDate: "",
    location: "",
  });

  const [attendanceRecords, setAttendanceRecords] = useState<Record<string, AttendanceRecord>>({});
  const [leaveBalances, setLeaveBalances] = useState<LeaveBalance[]>([]);
  const [leaveRequests, setLeaveRequests] = useState<LeaveRequest[]>([]);
  const [regularizations, setRegularizations] = useState<RegularizationRequest[]>([]);
  const [onDutyRequests, setOnDutyRequests] = useState<OnDutyRequest[]>([]);
  const [holidays, setHolidays] = useState<Holiday[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [settings, setSettings] = useState<UserSettings>({
    emailNotifications: true,
    pushNotifications: true,
    attendanceReminders: false,
    theme: "light",
    language: "English",
    timezone: "India Standard Time",
  });

  // Load all initial data from ApiService
  const refreshAllData = useCallback(async () => {
    try {
      setIsLoading(true);
      const [u, att, lb, lr, reg, od, hol, notifs, sett] = await Promise.all([
        ApiService.getCurrentUser(),
        ApiService.getAttendance(),
        ApiService.getLeaveBalance(),
        ApiService.getLeaveRequests(),
        ApiService.getRegularizationRequests(),
        ApiService.getOnDutyRequests(),
        ApiService.getHolidays(),
        ApiService.getNotifications(),
        ApiService.getSettings(),
      ]);

      setUser(u);
      setAttendanceRecords(att);
      setLeaveBalances(lb);
      setLeaveRequests(lr);
      setRegularizations(reg);
      setOnDutyRequests(od);
      setHolidays(hol);
      setNotifications(notifs);
      setSettings(sett);
    } catch (err) {
      console.error("Error loading data:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshAllData();
  }, [refreshAllData]);

  // Keep hash synced with active page
  const setActivePage = useCallback((page: Page) => {
    setActivePageState(page);
    window.location.hash = page;
  }, []);

  useEffect(() => {
    const handleHashChange = () => {
      const page = getInitialPageFromHash();
      setActivePageState(page);
    };
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  // Sync theme with DOM and localStorage
  const setTheme = useCallback(
    (theme: "light" | "dark") => {
      setSettings((prev) => ({ ...prev, theme }));
      ApiService.saveSettings({ theme });
      if (theme === "dark") {
        document.documentElement.classList.add("dark");
      } else {
        document.documentElement.classList.remove("dark");
      }
    },
    []
  );

  useEffect(() => {
    if (settings.theme === "dark") {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [settings.theme]);

  // Toast helpers
  const showToast = useCallback((msg: string) => {
    setToast(msg);
  }, []);

  const hideToast = useCallback(() => {
    setToast("");
  }, []);

  // Today computed record
  const todayIso = formatToISODate(new Date());
  const todayRecord: AttendanceRecord = useMemo(() => {
    if (attendanceRecords[todayIso]) {
      return attendanceRecords[todayIso];
    }
    return {
      id: `att-${todayIso}`,
      date: todayIso,
      status: "Pending",
      checkIn: "--:--",
      checkOut: "--:--",
      workingHours: "00h 00m",
      workingMinutes: 0,
      attendanceType: "Office",
    };
  }, [attendanceRecords, todayIso]);

  // Attendance state: "none" | "in" | "out"
  const attendanceState: AttendanceActionState = useMemo(() => {
    if (!todayRecord || todayRecord.checkIn === "--:--" || !todayRecord.checkIn) {
      return "none";
    }
    if (todayRecord.checkOut && todayRecord.checkOut !== "--:--") {
      return "out";
    }
    return "in";
  }, [todayRecord]);

  // Unread notification count
  const unreadNotificationsCount = useMemo(() => {
    return notifications.filter((n) => n.unread).length;
  }, [notifications]);

  // Actions
  const checkIn = useCallback(
    async (method: "standard" | "face" = "standard", location?: string) => {
      const updated = await ApiService.checkIn({ method, location });
      setAttendanceRecords((prev) => ({ ...prev, [todayIso]: updated }));
      const updatedNotifs = await ApiService.getNotifications();
      setNotifications(updatedNotifs);
      showToast(
        `${method === "face" ? "Face check-in" : "Check-in"} recorded at ${updated.checkIn}.`
      );
    },
    [todayIso, showToast]
  );

  const checkOut = useCallback(
    async (method: "standard" | "face" = "standard") => {
      const updated = await ApiService.checkOut({ method });
      setAttendanceRecords((prev) => ({ ...prev, [todayIso]: updated }));
      const updatedNotifs = await ApiService.getNotifications();
      setNotifications(updatedNotifs);
      showToast(
        `${method === "face" ? "Face check-out" : "Check-out"} recorded at ${updated.checkOut}. Total hours: ${updated.workingHours}.`
      );
    },
    [todayIso, showToast]
  );

  const applyLeave = useCallback(
    async (req: Omit<LeaveRequest, "id" | "appliedOn" | "status">) => {
      const newReq = await ApiService.applyLeave(req);
      setLeaveRequests((prev) => [newReq, ...prev]);
      const [balances, notifs] = await Promise.all([
        ApiService.getLeaveBalance(),
        ApiService.getNotifications(),
      ]);
      setLeaveBalances(balances);
      setNotifications(notifs);
      showToast(`Leave application for ${req.durationLabel} submitted.`);
    },
    [showToast]
  );

  const submitRegularization = useCallback(
    async (req: Omit<RegularizationRequest, "id" | "submittedOn" | "status">) => {
      const newReq = await ApiService.submitRegularization(req);
      setRegularizations((prev) => [newReq, ...prev]);
      const [records, notifs] = await Promise.all([
        ApiService.getAttendance(),
        ApiService.getNotifications(),
      ]);
      setAttendanceRecords(records);
      setNotifications(notifs);
      showToast("Regularization request submitted successfully.");
    },
    [showToast]
  );

  const submitOnDuty = useCallback(
    async (req: Omit<OnDutyRequest, "id" | "submittedOn" | "status">) => {
      const newReq = await ApiService.submitOnDuty(req);
      setOnDutyRequests((prev) => [newReq, ...prev]);
      const notifs = await ApiService.getNotifications();
      setNotifications(notifs);
      showToast("On Duty request submitted successfully.");
    },
    [showToast]
  );

  const markNotificationRead = useCallback(async (id: string) => {
    const updated = await ApiService.markNotificationAsRead(id);
    setNotifications(updated);
  }, []);

  const markAllNotificationsRead = useCallback(async () => {
    const updated = await ApiService.markAllNotificationsAsRead();
    setNotifications(updated);
  }, []);

  const clearNotifications = useCallback(async () => {
    const updated = await ApiService.clearAllNotifications();
    setNotifications(updated);
  }, []);

  const updateProfile = useCallback(
    async (partialProfile: Partial<UserProfile>) => {
      const updated = await ApiService.updateProfile(partialProfile);
      setUser(updated);
      showToast("Profile details updated successfully.");
    },
    [showToast]
  );

  const updateSettings = useCallback(
    async (partialSettings: Partial<UserSettings>) => {
      const updated = await ApiService.saveSettings(partialSettings);
      setSettings(updated);
      showToast("Preferences saved successfully.");
    },
    [showToast]
  );

  const resetDemoData = useCallback(async () => {
    await ApiService.resetAllDemoData();
    await refreshAllData();
    showToast("All demo data reset to defaults.");
  }, [refreshAllData, showToast]);

  const contextValue = useMemo(
    () => ({
      user,
      attendanceRecords,
      leaveBalances,
      leaveRequests,
      regularizations,
      onDutyRequests,
      holidays,
      notifications,
      settings,
      unreadNotificationsCount,
      todayRecord,
      attendanceState,
      activePage,
      setActivePage,
      toast,
      showToast,
      hideToast,
      isLoading,
      checkIn,
      checkOut,
      applyLeave,
      submitRegularization,
      submitOnDuty,
      markNotificationRead,
      markAllNotificationsRead,
      clearNotifications,
      updateProfile,
      updateSettings,
      setTheme,
      resetDemoData,
      refreshAllData,
    }),
    [
      user,
      attendanceRecords,
      leaveBalances,
      leaveRequests,
      regularizations,
      onDutyRequests,
      holidays,
      notifications,
      settings,
      unreadNotificationsCount,
      todayRecord,
      attendanceState,
      activePage,
      setActivePage,
      toast,
      showToast,
      hideToast,
      isLoading,
      checkIn,
      checkOut,
      applyLeave,
      submitRegularization,
      submitOnDuty,
      markNotificationRead,
      markAllNotificationsRead,
      clearNotifications,
      updateProfile,
      updateSettings,
      setTheme,
      resetDemoData,
      refreshAllData,
    ]
  );

  return <AppContext.Provider value={contextValue}>{children}</AppContext.Provider>;
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useApp must be used within an AppProvider");
  }
  return context;
}
