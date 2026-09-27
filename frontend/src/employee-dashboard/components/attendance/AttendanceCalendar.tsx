import React, { useState, useMemo } from "react";
import Button from "../common/Button";
import Icon from "../common/Icon";
import AttendanceDetailModal from "./AttendanceDetailModal";
import { useApp } from "../../context/AppContext";
import type { AttendanceRecord, Page } from "../../types";
import {
  formatToISODate,
  isToday,
  MONTH_NAMES_FULL,
} from "../../utils/dateUtils";

const statusCardStyles: Record<string, string> = {
  Present: "border-emerald-500 bg-emerald-50 text-emerald-800",
  "Work From Home": "border-violet-500 bg-violet-50 text-violet-800",
  "On Duty": "border-blue-500 bg-blue-50 text-blue-800",
  "On Leave": "border-amber-500 bg-amber-50 text-amber-800",
  "Missing Check-out": "border-orange-500 bg-orange-50 text-orange-800",
  Absent: "border-rose-500 bg-rose-50 text-rose-800",
  Weekend: "border-slate-300 bg-slate-50 text-slate-500",
};

export default function AttendanceCalendar({
  year,
  month,
  statusFilter,
  onRegularize,
}: {
  year: number;
  month: number;
  statusFilter: string;
  onRegularize: (dateIso: string, checkIn?: string) => void;
}) {
  const { attendanceRecords, setActivePage } = useApp();
  const [selectedRecord, setSelectedRecord] = useState<AttendanceRecord | null>(null);

  // Month days calculation
  const monthDays = new Date(year, month + 1, 0).getDate();
  // Start pad for Sunday start: 0 = Sun, 1 = Mon, ..., 6 = Sat
  const firstDayWeekday = new Date(year, month, 1).getDay();
  const totalCells = Math.ceil((firstDayWeekday + monthDays) / 7) * 7;
  const cells = Array.from({ length: totalCells }, (_, i) => i - firstDayWeekday + 1);

  return (
    <>
      <div className="overflow-x-auto">
        <div className="min-w-3xl">
          {/* Weekday headers */}
          <div className="grid grid-cols-7 bg-slate-50 text-center text-xs font-bold uppercase text-slate-500">
            {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => (
              <div key={day} className="border-b border-r border-slate-200 p-2">
                {day}
              </div>
            ))}
          </div>

          {/* Calendar grid */}
          <div className="grid grid-cols-7">
            {cells.map((day, index) => {
              const isValidDay = day > 0 && day <= monthDays;
              const isWeekendCell = index % 7 === 0 || index % 7 === 6;

              if (!isValidDay) {
                return (
                  <div
                    key={`empty-${index}`}
                    className="min-h-24 border-b border-r border-slate-200 p-2 bg-slate-50/50"
                  />
                );
              }

              const iso = formatToISODate(new Date(year, month, day));
              const isCurrentDay = isToday(iso);
              const todayIso = formatToISODate(new Date());
              const isPast = iso < todayIso;

              const record: AttendanceRecord = attendanceRecords[iso] || {
                id: `att-${iso}`,
                date: iso,
                status: isWeekendCell ? "Weekend" : isPast ? "Absent" : "Pending",
                checkIn: "--:--",
                checkOut: "--:--",
                workingHours: "00h 00m",
                workingMinutes: 0,
                attendanceType: "Office",
              };

              const matchesFilter =
                statusFilter === "All Status" ||
                statusFilter === "All" ||
                record.status === statusFilter ||
                (statusFilter === "On Leave" && record.status === "On Leave");

              return (
                <button
                  key={`day-${day}`}
                  type="button"
                  aria-label={`Date ${day} ${MONTH_NAMES_FULL[month]} ${year} - ${record.status}`}
                  onClick={() => setSelectedRecord(record)}
                  className={`min-h-24 border-b border-r border-slate-200 p-2 text-left transition hover:bg-slate-50/80 outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
                    isWeekendCell ? "bg-slate-50/70" : "bg-white"
                  } ${isCurrentDay ? "ring-2 ring-inset ring-indigo-500" : ""} ${
                    matchesFilter ? "opacity-100" : "opacity-25"
                  }`}
                >
                  <div className="mb-2 flex items-center justify-between">
                    <div
                      className={`text-xs font-bold ${
                        isCurrentDay
                          ? "grid size-6 place-items-center rounded-full bg-indigo-600 text-white"
                          : "text-slate-600"
                      }`}
                    >
                      {day}
                    </div>
                  </div>

                  {!isWeekendCell && (
                    <div
                      className={`rounded-md border-l-2 p-1.5 shadow-2xs ${
                        statusCardStyles[record.status] ||
                        "border-slate-400 bg-slate-100 text-slate-700"
                      }`}
                    >
                      <div className="truncate text-xs font-semibold">{record.status}</div>
                      <div className="mt-0.5 truncate text-xs opacity-80 font-medium">
                        {record.workingHours !== "00h 00m"
                          ? record.workingHours
                          : record.status === "On Leave"
                          ? "Leave"
                          : "--:--"}
                      </div>
                    </div>
                  )}

                  {isWeekendCell && (
                    <div className="type-caption text-slate-400 font-medium">Weekend</div>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {selectedRecord && (
        <AttendanceDetailModal
          record={selectedRecord}
          close={() => setSelectedRecord(null)}
          onRegularize={(dateIso, checkIn) => {
            setSelectedRecord(null);
            onRegularize(dateIso, checkIn);
          }}
          onViewDetails={(page) => {
            setSelectedRecord(null);
            setActivePage(page as Page);
          }}
        />
      )}
    </>
  );
}
