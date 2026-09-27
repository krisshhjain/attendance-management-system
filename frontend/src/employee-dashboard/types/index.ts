export type Page =
  | "dashboard"
  | "attendance"
  | "leave"
  | "regularization"
  | "onduty"
  | "notifications"
  | "profile"
  | "settings";

export type IconName =
  | "grid"
  | "calendar"
  | "leave"
  | "refresh"
  | "briefcase"
  | "bell"
  | "user"
  | "settings"
  | "clock"
  | "camera"
  | "menu"
  | "close"
  | "chevron"
  | "search"
  | "check"
  | "upload"
  | "list"
  | "shield"
  | "sun"
  | "moon"
  | "filter"
  | "plus"
  | "arrowLeft"
  | "arrowRight";

export type AttendanceStatus =
  | "Present"
  | "Absent"
  | "Late"
  | "Work From Home"
  | "On Duty"
  | "On Leave"
  | "Half Day"
  | "Holiday"
  | "Weekend"
  | "Missing Check-out"
  | "Pending";

export interface UserProfile {
  id: string;
  name: string;
  employeeId: string;
  email: string;
  phone: string;
  department: string;
  designation: string;
  manager: string;
  joiningDate: string;
  avatarUrl?: string;
  location: string;
}

export interface AttendanceRecord {
  id: string;
  date: string; // YYYY-MM-DD
  status: AttendanceStatus;
  checkIn: string; // e.g. "09:15 AM" or "--:--"
  checkOut: string; // e.g. "05:45 PM" or "--:--"
  workingHours: string; // e.g. "08h 30m"
  workingMinutes: number; // for charts and calculations
  breakHours?: string;
  attendanceType: "Office" | "Work From Home" | "On Duty";
  location?: string;
  notes?: string;
}

export type LeaveStatus = "Pending" | "Approved" | "Rejected";

export interface LeaveRequest {
  id: string;
  leaveType: string;
  startDate: string; // YYYY-MM-DD
  endDate: string; // YYYY-MM-DD
  duration: number; // days
  durationLabel: string; // "2 days"
  reason: string;
  status: LeaveStatus;
  appliedOn: string; // YYYY-MM-DD
  reviewedOn?: string;
  reviewedBy?: string;
  attachmentName?: string;
}

export interface LeaveBalance {
  type: string;
  total: number;
  used: number;
  available: number;
  pending: number;
}

export type RegularizationStatus = "Pending" | "Approved" | "Rejected";

export interface RegularizationRequest {
  id: string;
  periodType: "Day" | "Week" | "Month";
  date: string;
  startDate?: string;
  endDate?: string;
  checkIn: string;
  checkOut: string;
  totalHours: string;
  reason: string;
  description: string;
  status: RegularizationStatus;
  submittedOn: string;
  attachmentName?: string;
}

export type OnDutyStatus = "Pending" | "Approved" | "Rejected";

export interface OnDutyRequest {
  id: string;
  date: string;
  startDate?: string;
  endDate?: string;
  startTime: string;
  endTime: string;
  location: string;
  purpose: string;
  description: string;
  status: OnDutyStatus;
  submittedOn: string;
  attachmentName?: string;
}

export interface Holiday {
  id: string;
  name: string;
  date: string; // YYYY-MM-DD
  type: "Gazetted" | "Restricted" | "Company";
  description?: string;
}

export interface NotificationItem {
  id: string;
  title: string;
  message: string;
  timestamp: string; // ISO string
  timeAgo: string;
  icon: IconName;
  unread: boolean;
  link?: Page;
}

export interface UserSettings {
  emailNotifications: boolean;
  pushNotifications: boolean;
  attendanceReminders: boolean;
  theme: "light" | "dark";
  language: string;
  timezone: string;
}

export type AttendanceActionState = "none" | "in" | "out";
