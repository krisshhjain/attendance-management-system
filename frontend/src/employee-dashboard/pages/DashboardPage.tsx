import React, { useMemo } from "react";
import PageHeader from "../components/common/PageHeader";
import Card from "../components/common/Card";
import SectionTitle from "../components/common/SectionTitle";
import Button from "../components/common/Button";
import Badge from "../components/common/Badge";
import Icon from "../components/common/Icon";
import DataTable from "../components/common/DataTable";
import WeeklyAttendance from "../components/attendance/WeeklyAttendance";
import type { ModalType } from "../components/attendance/AttendanceModal";
import { useApp } from "../context/AppContext";
import {
  getGreeting,
  formatDateFullDisplay,
  formatDateDisplay,
  formatToISODate,
  calculateCurrentWorkingHours,
} from "../utils/dateUtils";

export default function DashboardPage({
  openModal,
  onRegularize,
}: {
  openModal: (modal: ModalType) => void;
  onRegularize: (dateIso: string, checkIn?: string) => void;
}) {
  const { user, todayRecord, attendanceState, holidays, attendanceRecords, setActivePage } =
    useApp();

  const checkedIn = attendanceState !== "none";
  const checkedOut = attendanceState === "out";

  // Dynamic working hours for today: if checked in but not checked out, compute up to now
  const displayWorkingHours = useMemo(() => {
    if (checkedOut) {
      return todayRecord.workingHours;
    }
    if (checkedIn && todayRecord.checkIn && todayRecord.checkIn !== "--:--") {
      return calculateCurrentWorkingHours(todayRecord.checkIn).formatted;
    }
    return "00h 00m";
  }, [checkedIn, checkedOut, todayRecord]);

  // Filter upcoming holidays (from today onwards)
  const todayIso = formatToISODate(new Date());
  const upcomingHolidays = useMemo(() => {
    const list = (holidays || []).filter((h) => h.date >= todayIso);
    // If fewer than 3 upcoming in current year, take next available or fallback
    return list.slice(0, 3);
  }, [holidays, todayIso]);

  // Dynamic recent attendance: past 5 working days from attendanceRecords
  const recentAttendanceRows = useMemo(() => {
    const records = Object.values(attendanceRecords || {})
      .filter((rec) => rec.date <= todayIso && rec.status !== "Weekend")
      .sort((a, b) => b.date.localeCompare(a.date))
      .slice(0, 4);

    return records.map((rec) => [
      <span key={`date-${rec.id}`} className="font-semibold text-slate-700">
        {formatDateDisplay(rec.date)}
      </span>,
      <Badge key={`badge-${rec.id}`} status={rec.status} />,
      rec.checkIn,
      rec.checkOut === "--:--" ? "Not recorded" : rec.checkOut,
      rec.workingHours,
    ]);
  }, [attendanceRecords, todayIso]);

  const greetingText = getGreeting(user.name);
  const subtitleText = `Here's your attendance overview for ${formatDateFullDisplay(new Date())}.`;

  const holidayColors = ["bg-indigo-500", "bg-amber-500", "bg-emerald-500"];

  return (
    <>
      <PageHeader title={greetingText} subtitle={subtitleText} />

      {/* Today's Attendance Overview Card */}
      <Card className="mb-5 overflow-hidden border-indigo-200">
        <div className="grid lg:grid-cols-[1.2fr_1fr]">
          <div className="border-b border-slate-200 p-4 lg:border-b-0 lg:border-r">
            <div className="mb-3 flex items-start justify-between">
              <div>
                <div className="type-meta font-semibold uppercase tracking-wide text-slate-500">
                  Today's Attendance
                </div>
                <div className="mt-1 flex items-center gap-2 text-sm font-semibold text-slate-900">
                  <span
                    className={`size-2.5 rounded-full ${
                      checkedIn ? "bg-emerald-500 animate-pulse" : "bg-slate-300"
                    }`}
                  />
                  {checkedOut
                    ? "Checked Out"
                    : checkedIn
                    ? "Present (In Progress)"
                    : "Not Checked In"}
                </div>
              </div>
              <Badge status={checkedOut ? "Present" : checkedIn ? "Present" : "Pending"} />
            </div>

            <div className="grid grid-cols-3 divide-x divide-slate-200 rounded-lg bg-slate-50 p-3">
              <div className="px-3">
                <div className="type-meta font-medium text-slate-500">Check In</div>
                <div className="mt-1 text-xs font-semibold text-slate-800">
                  {todayRecord.checkIn}
                </div>
              </div>
              <div className="px-3">
                <div className="type-meta font-medium text-slate-500">Check Out</div>
                <div className="mt-1 text-xs font-semibold text-slate-800">
                  {todayRecord.checkOut === "--:--" ? "--:--" : todayRecord.checkOut}
                </div>
              </div>
              <div className="px-3">
                <div className="type-meta font-medium text-slate-500">Working</div>
                <div className="mt-1 text-xs font-semibold text-slate-800">
                  {displayWorkingHours}
                </div>
              </div>
            </div>
          </div>

          <div className="p-4">
            <div className="type-meta mb-2 font-semibold uppercase tracking-wide text-slate-500">
              Quick actions
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              <Button
                className="min-h-11 sm:min-h-10"
                disabled={checkedIn}
                onClick={() => openModal("checkin")}
              >
                <Icon name="clock" className="size-4" />
                {checkedIn ? `Checked In · ${todayRecord.checkIn}` : "Check In"}
              </Button>

              <Button
                className="min-h-11 sm:min-h-10"
                variant="secondary"
                disabled={!checkedIn || checkedOut}
                onClick={() => openModal("checkout")}
              >
                <Icon name="clock" className="size-4" />
                {checkedOut ? `Checked Out · ${todayRecord.checkOut}` : "Check Out"}
              </Button>

              <Button
                className="min-h-11 sm:min-h-10"
                variant="secondary"
                disabled={checkedIn}
                onClick={() => openModal("facein")}
              >
                <Icon name="camera" className="size-4" />
                Face Check In
              </Button>

              <Button
                className="min-h-11 sm:min-h-10"
                variant="secondary"
                disabled={!checkedIn || checkedOut}
                onClick={() => openModal("faceout")}
              >
                <Icon name="camera" className="size-4" />
                Face Check Out
              </Button>
            </div>
          </div>
        </div>
      </Card>

      {/* Weekly Zoho Timeline Component */}
      <div className="mb-5">
        <WeeklyAttendance onRegularize={onRegularize} />
      </div>

      {/* Upcoming Holidays */}
      <Card className="mb-5">
        <SectionTitle
          title="Upcoming Holidays"
          subtitle="Company calendar based on current date"
        />
        {upcomingHolidays.length > 0 ? (
          <div className="grid gap-px bg-slate-200 sm:grid-cols-2 lg:grid-cols-3">
            {upcomingHolidays.map((holiday, idx) => (
              <div key={holiday.id} className="flex items-center gap-3 bg-white px-5 py-3">
                <span
                  className={`size-2 rounded-full ${
                    holidayColors[idx % holidayColors.length]
                  }`}
                />
                <div className="min-w-0 flex-1">
                  <div className="truncate text-xs font-medium text-slate-700">
                    {holiday.name}
                  </div>
                  <div className="type-caption mt-0.5 font-normal text-slate-500">
                    {formatDateDisplay(holiday.date)}
                  </div>
                </div>
                <Icon name="calendar" className="size-4 text-slate-400" />
              </div>
            ))}
          </div>
        ) : (
          <div className="p-6 text-center text-xs text-slate-500">
            No upcoming company holidays remaining for this period.
          </div>
        )}
      </Card>

      {/* Recent Attendance */}
      <Card>
        <SectionTitle
          title="Recent Attendance"
          subtitle="Your latest attendance records"
          action={
            <Button variant="secondary" onClick={() => setActivePage("attendance")}>
              View Full Attendance <Icon name="chevron" className="size-4" />
            </Button>
          }
        />
        <DataTable
          headers={["Date", "Status", "Check In", "Check Out", "Working Hours"]}
          rows={recentAttendanceRows}
          emptyMessage="No recent attendance records available."
        />
      </Card>
    </>
  );
}
