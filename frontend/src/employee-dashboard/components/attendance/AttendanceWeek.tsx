import React from "react";
import Badge from "../common/Badge";
import type { AttendanceRecord } from "../../types";
import { formatToISODate, isToday, DAY_NAMES_SHORT, getWeekDates } from "../../utils/dateUtils";

export default function AttendanceWeek({
  baseDate,
  attendanceRecords,
  onSelectRecord,
}: {
  baseDate: Date;
  attendanceRecords: Record<string, AttendanceRecord>;
  onSelectRecord: (record: AttendanceRecord) => void;
}) {
  const weekDays = getWeekDates(baseDate, 0);

  return (
    <div className="overflow-x-auto p-4">
      <div className="grid min-w-4xl grid-cols-7 gap-3">
        {weekDays.map((dateObj) => {
          const iso = formatToISODate(dateObj);
          const dayName = DAY_NAMES_SHORT[dateObj.getDay()];
          const dateNumber = String(dateObj.getDate());
          const isCurrent = isToday(iso);
          const isWeekendDay = dateObj.getDay() === 0 || dateObj.getDay() === 6;

          const todayIso = formatToISODate(new Date());
          const isPast = iso < todayIso;

          const record: AttendanceRecord = attendanceRecords[iso] || {
            id: `att-${iso}`,
            date: iso,
            status: isWeekendDay ? "Weekend" : isPast ? "Absent" : "Pending",
            checkIn: "--:--",
            checkOut: "--:--",
            workingHours: "00h 00m",
            workingMinutes: 0,
            attendanceType: "Office",
          };

          return (
            <button
              key={iso}
              type="button"
              aria-label={`View ${dayName} ${dateNumber}`}
              onClick={() => onSelectRecord(record)}
              className={`rounded-lg border p-3 text-left transition hover:shadow-xs outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
                isCurrent
                  ? "border-indigo-400 bg-indigo-50/40 ring-1 ring-inset ring-indigo-300"
                  : "border-slate-200 bg-white hover:bg-slate-50"
              }`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-xs font-semibold text-slate-400 uppercase">{dayName}</div>
                  <div className="mt-1 text-lg font-bold text-slate-800">{dateNumber}</div>
                </div>
                {isCurrent && (
                  <span className="rounded-full bg-indigo-600 px-2 py-0.5 text-xs font-semibold text-white">
                    Today
                  </span>
                )}
              </div>

              <div className="mt-4">
                <Badge status={record.status} />
              </div>

              <div className="mt-4 space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-400">In</span>
                  <span className="font-semibold text-slate-700">{record.checkIn}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Out</span>
                  <span className="font-semibold text-slate-700">
                    {record.checkOut === "--:--" ? "Not recorded" : record.checkOut}
                  </span>
                </div>
                <div className="flex justify-between border-t border-slate-100 pt-2">
                  <span className="text-slate-400">Total</span>
                  <span className="font-bold text-slate-800">{record.workingHours}</span>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
