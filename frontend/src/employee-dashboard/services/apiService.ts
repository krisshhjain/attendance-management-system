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
} from "../utils/dateUtils";
import { StorageService } from "./storageService";

StorageService.initialize();

export const ApiService = {
  // --- USER & PROFILE ---
  async getCurrentUser(): Promise<UserProfile> {
    return StorageService.getUser();
  },

  async updateProfile(user: Partial<UserProfile>): Promise<UserProfile> {
    const current = StorageService.getUser();
    const updated = { ...current, ...user };
    StorageService.saveUser(updated);
    return updated;
  },

  // --- ATTENDANCE ---
  async getAttendance(): Promise<Record<string, AttendanceRecord>> {
    return StorageService.getAttendanceRecords();
  },

  async getAttendanceByDate(dateIso: string): Promise<AttendanceRecord | null> {
    const records = StorageService.getAttendanceRecords();
    return records[dateIso] || null;
  },

  async checkIn(options?: { method?: "standard" | "face"; location?: string }): Promise<AttendanceRecord> {
    const now = new Date();
    const iso = formatToISODate(now);
    const timeStr = formatTimeDisplay(now);
    const records = StorageService.getAttendanceRecords();

    const existing = records[iso] || {
      id: `att-${iso}`,
      date: iso,
      status: "Present",
      checkIn: "--:--",
      checkOut: "--:--",
      workingHours: "00h 00m",
      workingMinutes: 0,
      attendanceType: "Office",
    };

    const updated: AttendanceRecord = {
      ...existing,
      status: "Present",
      checkIn: timeStr,
      notes: options?.method === "face" ? "Verified via Biometric Face Scan" : "Web Check-In",
      location: options?.location || existing.location || "Office",
    };

    records[iso] = updated;
    StorageService.saveAttendanceRecords(records);

    // Create a real notification
    await this.createNotification({
      title: "Check-in successful",
      message: `You checked in at ${timeStr} via ${options?.method === "face" ? "Face Verification" : "Web portal"}.`,
      icon: options?.method === "face" ? "camera" : "clock",
      link: "dashboard",
    });

    return updated;
  },

  async checkOut(options?: { method?: "standard" | "face" }): Promise<AttendanceRecord> {
    const now = new Date();
    const iso = formatToISODate(now);
    const timeStr = formatTimeDisplay(now);
    const records = StorageService.getAttendanceRecords();

    const existing = records[iso];
    if (!existing || existing.checkIn === "--:--") {
      throw new Error("Cannot check out without checking in first.");
    }

    const { formatted, minutes } = calculateWorkingHours(existing.checkIn, timeStr);

    const updated: AttendanceRecord = {
      ...existing,
      checkOut: timeStr,
      workingHours: formatted,
      workingMinutes: minutes,
      notes: `${existing.notes ? existing.notes + " · " : ""}${options?.method === "face" ? "Checked out via Face Scan" : "Web Check-Out"}`,
    };

    records[iso] = updated;
    StorageService.saveAttendanceRecords(records);

    // Create a real notification
    await this.createNotification({
      title: "Check-out completed",
      message: `You checked out at ${timeStr}. Total working duration: ${formatted}.`,
      icon: "check",
      link: "dashboard",
    });

    return updated;
  },

  // --- LEAVE MANAGEMENT ---
  async getLeaveRequests(): Promise<LeaveRequest[]> {
    return StorageService.getLeaveRequests();
  },

  async getLeaveBalance(): Promise<LeaveBalance[]> {
    return StorageService.getLeaveBalances();
  },

  async applyLeave(request: Omit<LeaveRequest, "id" | "appliedOn" | "status">): Promise<LeaveRequest> {
    const requests = StorageService.getLeaveRequests();
    const balances = StorageService.getLeaveBalances();
    const now = new Date();
    const year = now.getFullYear();

    const newRequest: LeaveRequest = {
      ...request,
      id: `LR-${year}-${String(requests.length + 1).padStart(2, "0")}`,
      appliedOn: formatToISODate(now),
      status: "Pending",
    };

    requests.unshift(newRequest);
    StorageService.saveLeaveRequests(requests);

    // Update pending balance
    const updatedBalances = balances.map((bal) => {
      if (bal.type === request.leaveType) {
        return {
          ...bal,
          pending: bal.pending + request.duration,
        };
      }
      return bal;
    });
    StorageService.saveLeaveBalances(updatedBalances);

    // Create notification
    await this.createNotification({
      title: "Leave application submitted",
      message: `Your ${request.leaveType} request for ${request.durationLabel} is awaiting manager review.`,
      icon: "leave",
      link: "leave",
    });

    return newRequest;
  },

  // --- REGULARIZATION ---
  async getRegularizationRequests(): Promise<RegularizationRequest[]> {
    return StorageService.getRegularizations();
  },

  async submitRegularization(
    request: Omit<RegularizationRequest, "id" | "submittedOn" | "status">
  ): Promise<RegularizationRequest> {
    const requests = StorageService.getRegularizations();
    const now = new Date();
    const year = now.getFullYear();

    const newReq: RegularizationRequest = {
      ...request,
      id: `REG-${year}-${String(requests.length + 1).padStart(2, "0")}`,
      submittedOn: formatDateDisplay(now),
      status: "Pending",
    };

    requests.unshift(newReq);
    StorageService.saveRegularizations(requests);

    // Also update attendance record for that date if it had Missing Check-out
    if (request.startDate) {
      const records = StorageService.getAttendanceRecords();
      if (records[request.startDate]) {
        records[request.startDate] = {
          ...records[request.startDate],
          checkIn: request.checkIn || records[request.startDate].checkIn,
          checkOut: request.checkOut || records[request.startDate].checkOut,
          workingHours: request.totalHours || records[request.startDate].workingHours,
          notes: `Regularization requested: ${request.reason}`,
        };
        StorageService.saveAttendanceRecords(records);
      }
    }

    // Create notification
    await this.createNotification({
      title: "Regularization request submitted",
      message: `Your request for ${request.date} (${request.reason}) has been forwarded to HR.`,
      icon: "refresh",
      link: "regularization",
    });

    return newReq;
  },

  // --- ON DUTY ---
  async getOnDutyRequests(): Promise<OnDutyRequest[]> {
    return StorageService.getOnDutyRequests();
  },

  async submitOnDuty(request: Omit<OnDutyRequest, "id" | "submittedOn" | "status">): Promise<OnDutyRequest> {
    const requests = StorageService.getOnDutyRequests();
    const now = new Date();
    const year = now.getFullYear();

    const newReq: OnDutyRequest = {
      ...request,
      id: `OD-${year}-${String(requests.length + 1).padStart(2, "0")}`,
      submittedOn: formatDateDisplay(now),
      status: "Pending",
    };

    requests.unshift(newReq);
    StorageService.saveOnDutyRequests(requests);

    await this.createNotification({
      title: "On Duty request submitted",
      message: `Your official work request for ${request.location} is awaiting manager approval.`,
      icon: "briefcase",
      link: "onduty",
    });

    return newReq;
  },

  // --- HOLIDAYS ---
  async getHolidays(): Promise<Holiday[]> {
    return StorageService.getHolidays();
  },

  // --- NOTIFICATIONS ---
  async getNotifications(): Promise<NotificationItem[]> {
    return StorageService.getNotifications();
  },

  async markNotificationAsRead(id: string): Promise<NotificationItem[]> {
    const notifications = StorageService.getNotifications().map((item) =>
      item.id === id ? { ...item, unread: false } : item
    );
    StorageService.saveNotifications(notifications);
    return notifications;
  },

  async markAllNotificationsAsRead(): Promise<NotificationItem[]> {
    const notifications = StorageService.getNotifications().map((item) => ({ ...item, unread: false }));
    StorageService.saveNotifications(notifications);
    return notifications;
  },

  async clearAllNotifications(): Promise<NotificationItem[]> {
    StorageService.saveNotifications([]);
    return [];
  },

  async createNotification(
    notif: Omit<NotificationItem, "id" | "timestamp" | "timeAgo" | "unread">
  ): Promise<NotificationItem> {
    const notifications = StorageService.getNotifications();
    const newNotif: NotificationItem = {
      ...notif,
      id: `notif-${Date.now()}`,
      timestamp: new Date().toISOString(),
      timeAgo: "Just now",
      unread: true,
    };
    notifications.unshift(newNotif);
    StorageService.saveNotifications(notifications);
    return newNotif;
  },

  // --- SETTINGS ---
  async getSettings(): Promise<UserSettings> {
    return StorageService.getSettings();
  },

  async saveSettings(settings: Partial<UserSettings>): Promise<UserSettings> {
    const current = StorageService.getSettings();
    const updated = { ...current, ...settings };
    StorageService.saveSettings(updated);
    return updated;
  },

  // --- RESET ALL ---
  async resetAllDemoData(): Promise<void> {
    StorageService.resetAllData();
  },
};
