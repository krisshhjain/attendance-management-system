import React, { useState, useMemo } from "react";
import PageHeader from "../components/common/PageHeader";
import Card from "../components/common/Card";
import SectionTitle from "../components/common/SectionTitle";
import Button from "../components/common/Button";
import Field from "../components/common/Field";
import Icon from "../components/common/Icon";
import Badge from "../components/common/Badge";
import DataTable from "../components/common/DataTable";
import AttendanceCalendar from "../components/attendance/AttendanceCalendar";
import AttendanceWeek from "../components/attendance/AttendanceWeek";
import AttendanceList from "../components/attendance/AttendanceList";
import AttendanceDetailModal from "../components/attendance/AttendanceDetailModal";
import RegularizationPage from "./RegularizationPage";
import OnDutyPage from "./OnDutyPage";
import { useApp } from "../context/AppContext";
import {
  MONTH_NAMES_FULL,
  formatDateDisplay,
  formatToISODate,
} from "../utils/dateUtils";
import type { AttendanceRecord, Page } from "../types";

export default function AttendancePage({
  onRegularize,
}: {
  onRegularize: (dateIso: string, checkIn?: string) => void;
}) {
  const { attendanceRecords, setActivePage } = useApp();

  const [tab, setTab] = useState<"Attendance Summary" | "Regularization" | "On Duty">(
    "Attendance Summary"
  );
  const [calendarView, setCalendarView] = useState<"Month" | "Week" | "List">("Month");

  const now = new Date();
  const [selectedYear, setSelectedYear] = useState(now.getFullYear());
  const [selectedMonth, setSelectedMonth] = useState(now.getMonth());
  const [statusFilter, setStatusFilter] = useState("All Status");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedDetailRecord, setSelectedDetailRecord] = useState<AttendanceRecord | null>(null);

  // Month navigation
  const prevMonth = () => {
    if (selectedMonth === 0) {
      setSelectedMonth(11);
      setSelectedYear((y) => y - 1);
    } else {
      setSelectedMonth((m) => m - 1);
    }
  };

  const nextMonth = () => {
    if (selectedMonth === 11) {
      setSelectedMonth(0);
      setSelectedYear((y) => y + 1);
    } else {
      setSelectedMonth((m) => m + 1);
    }
  };

  const goToToday = () => {
    const cur = new Date();
    setSelectedMonth(cur.getMonth());
    setSelectedYear(cur.getFullYear());
  };

  // Calculate dynamic attendance stats for the selected month
  const monthlyStats = useMemo(() => {
    let present = 0;
    let absent = 0;
    let paidLeave = 0;
    let unpaidLeave = 0;
    let onDuty = 0;
    let wfh = 0;

    Object.values(attendanceRecords || {}).forEach((record) => {
      const [y, m] = record.date.split("-").map(Number);
      if (y === selectedYear && m - 1 === selectedMonth) {
        if (record.status === "Present") present++;
        else if (record.status === "Absent") absent++;
        else if (record.status === "On Leave") paidLeave++;
        else if (record.status === "On Duty") onDuty++;
        else if (record.status === "Work From Home") wfh++;
      }
    });

    return [
      { label: "Present", value: `${present} days` },
      { label: "Absent", value: `${absent} days` },
      { label: "Paid Leave", value: `${paidLeave} days` },
      { label: "Unpaid Leave", value: `${unpaidLeave} days` },
      { label: "On Duty", value: `${onDuty} days` },
      { label: "Work From Home", value: `${wfh} days` },
    ];
  }, [attendanceRecords, selectedYear, selectedMonth]);

  // History table rows for selected month
  const historyRows = useMemo(() => {
    const records = Object.values(attendanceRecords || {})
      .filter((rec) => {
        const [y, m] = rec.date.split("-").map(Number);
        if (y !== selectedYear || m - 1 !== selectedMonth) return false;
        if (rec.status === "Weekend") return false;
        return true;
      })
      .sort((a, b) => b.date.localeCompare(a.date));

    return records.map((rec) => [
      <span key={`hist-${rec.id}`} className="font-semibold text-slate-700">
        {formatDateDisplay(rec.date)}
      </span>,
      <Badge key={`badge-${rec.id}`} status={rec.status} />,
      rec.checkIn,
      rec.checkOut === "--:--" ? "Not recorded" : rec.checkOut,
      rec.workingHours,
    ]);
  }, [attendanceRecords, selectedYear, selectedMonth]);

  if (tab === "Regularization") {
    return <RegularizationPage back={() => setTab("Attendance Summary")} />;
  }
  if (tab === "On Duty") {
    return <OnDutyPage back={() => setTab("Attendance Summary")} />;
  }

  return (
    <>
      <PageHeader
        title="My Attendance"
        subtitle="View your attendance history and daily working hours."
      />

      {/* Tabs */}
      <div className="mb-5 flex gap-1 overflow-x-auto border-b border-slate-200">
        {(["Attendance Summary", "Regularization", "On Duty"] as const).map((item) => (
          <Button
            key={item}
            variant="ghost"
            onClick={() => setTab(item)}
            className={`shrink-0 rounded-none border-b-2 px-4 py-2.5 font-semibold ${
              tab === item
                ? "border-indigo-600 text-indigo-700"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {item}
          </Button>
        ))}
      </div>

      {/* Dynamic Monthly Stats */}
      <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-6">
        {monthlyStats.map(({ label, value }) => (
          <Card key={label} className="p-3">
            <div className="text-xs font-medium text-slate-500">{label}</div>
            <div className="mt-1 text-base font-bold text-slate-800">{value}</div>
          </Card>
        ))}
      </div>

      {/* Calendar Card */}
      <Card className="mb-5 overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 p-4">
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              className="px-3"
              onClick={prevMonth}
              ariaLabel="Previous month"
            >
              ‹
            </Button>
            <div className="min-w-40 text-center text-sm font-bold text-slate-800">
              {MONTH_NAMES_FULL[selectedMonth]} {selectedYear}
            </div>
            <Button
              variant="secondary"
              className="px-3"
              onClick={nextMonth}
              ariaLabel="Next month"
            >
              ›
            </Button>
            <Button variant="ghost" className="text-indigo-600 font-semibold" onClick={goToToday}>
              Today
            </Button>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="w-36">
              <Field
                label=""
                value={statusFilter}
                onChange={setStatusFilter}
                options={[
                  "All Status",
                  "Present",
                  "Absent",
                  "On Leave",
                  "Work From Home",
                  "On Duty",
                ]}
              />
            </div>

            {calendarView === "List" && (
              <div className="w-44">
                <Field
                  label=""
                  placeholder="Search date or status…"
                  value={searchQuery}
                  onChange={setSearchQuery}
                />
              </div>
            )}

            <div className="flex rounded-lg border border-slate-300 bg-white p-1">
              {(["Month", "Week", "List"] as const).map((view) => (
                <Button
                  key={view}
                  variant="ghost"
                  className={`min-h-8 px-3 text-xs ${
                    calendarView === view ? "bg-indigo-50 text-indigo-700 font-semibold" : ""
                  }`}
                  onClick={() => setCalendarView(view)}
                >
                  {view === "List" ? (
                    <Icon name="list" className="size-3.5" />
                  ) : (
                    <Icon name="calendar" className="size-3.5" />
                  )}
                  {view}
                </Button>
              ))}
            </div>
          </div>
        </div>

        {calendarView === "Month" ? (
          <AttendanceCalendar
            year={selectedYear}
            month={selectedMonth}
            statusFilter={statusFilter}
            onRegularize={onRegularize}
          />
        ) : calendarView === "Week" ? (
          <AttendanceWeek
            baseDate={new Date(selectedYear, selectedMonth, 15)}
            attendanceRecords={attendanceRecords}
            onSelectRecord={setSelectedDetailRecord}
          />
        ) : (
          <AttendanceList
            year={selectedYear}
            month={selectedMonth}
            statusFilter={statusFilter}
            searchQuery={searchQuery}
            attendanceRecords={attendanceRecords}
            onSelectRecord={setSelectedDetailRecord}
          />
        )}
      </Card>

      {/* Attendance History Section */}
      <Card>
        <SectionTitle
          title="Attendance History"
          subtitle={`Detailed daily records for ${MONTH_NAMES_FULL[selectedMonth]} ${selectedYear}`}
        />
        <DataTable
          headers={["Date", "Status", "Check In", "Check Out", "Working Hours"]}
          rows={historyRows}
          emptyMessage={`No attendance history found for ${MONTH_NAMES_FULL[selectedMonth]} ${selectedYear}.`}
        />
      </Card>

      {selectedDetailRecord && (
        <AttendanceDetailModal
          record={selectedDetailRecord}
          close={() => setSelectedDetailRecord(null)}
          onRegularize={(dateIso, checkIn) => {
            setSelectedDetailRecord(null);
            onRegularize(dateIso, checkIn);
          }}
          onViewDetails={(page) => {
            setSelectedDetailRecord(null);
            setActivePage(page as Page);
          }}
        />
      )}
    </>
  );
}
