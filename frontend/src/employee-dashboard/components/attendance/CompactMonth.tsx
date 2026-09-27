import React from "react";
import type { AttendanceRecord } from "../../types";
import { formatToISODate, isToday } from "../../utils/dateUtils";

export default function CompactMonth({
  year,
  month,
  attendanceRecords,
  statusDot,
  onSelect,
}: {
  year: number;
  month: number;
  attendanceRecords: Record<string, AttendanceRecord>;
  statusDot: Record<string, string>;
  onSelect: (record: AttendanceRecord) => void;
}) {
  const monthDays = new Date(year, month + 1, 0).getDate();
  // Monday start: Sun = 0 -> 6, Mon = 1 -> 0, etc.
  const startPad = (new Date(year, month, 1).getDay() + 6) % 7;
  const cellCount = Math.ceil((startPad + monthDays) / 7) * 7;
  const cells = Array.from({ length: cellCount }, (_, index) => index - startPad + 1);

  return (
    <div className="overflow-x-auto">
      <div className="min-w-2xl">
        <div className="grid grid-cols-7 bg-slate-50 text-center text-xs font-bold text-slate-500">
          {["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"].map((day) => (
            <div key={day} className="border-b border-r border-slate-200 py-1.5">
              {day}
            </div>
          ))}
        </div>

        <div className="grid grid-cols-7">
          {cells.map((day, index) => {
            const isValidDay = day > 0 && day <= monthDays;
            if (!isValidDay) {
              return (
                <div
                  key={`pad-${index}`}
                  className="min-h-12 border-b border-r border-slate-200 p-1.5 bg-slate-50/40"
                />
              );
            }

            const iso = formatToISODate(new Date(year, month, day));
            const dayOfWeek = (index % 7);
            const isWeekendDay = dayOfWeek === 5 || dayOfWeek === 6;

            const todayIso = formatToISODate(new Date());
            const isPast = iso < todayIso;

            const existingRecord = attendanceRecords[iso];
            const record: AttendanceRecord = existingRecord || {
              id: `att-${iso}`,
              date: iso,
              status: isWeekendDay ? "Weekend" : isPast ? "Absent" : "Pending",
              checkIn: "--:--",
              checkOut: "--:--",
              workingHours: "00h 00m",
              workingMinutes: 0,
              attendanceType: "Office",
            };

            const isCurrent = isToday(iso);
            const status = record.status;
            const hoursDisplay = record.workingHours;

            return (
              <button
                key={`day-${day}`}
                type="button"
                aria-label={`View attendance for day ${day}`}
                onClick={() => onSelect(record)}
                className={`min-h-12 border-b border-r border-slate-200 p-1.5 text-left hover:bg-slate-50 transition outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
                  isCurrent ? "bg-indigo-50/60 ring-1 ring-inset ring-indigo-300" : ""
                }`}
              >
                <div className="text-xs font-bold text-slate-600 flex items-center justify-between">
                  <span>{day}</span>
                  {isCurrent && (
                    <span className="size-1.5 rounded-full bg-indigo-600 shrink-0" />
                  )}
                </div>
                <div className="mt-1 flex items-center gap-1">
                  <span
                    className={`size-1.5 shrink-0 rounded-full ${
                      statusDot[status] || "bg-slate-400"
                    }`}
                  />
                  <span className="truncate text-xs font-medium text-slate-600">
                    {status === "Work From Home" ? "WFH" : status}
                  </span>
                </div>
                {hoursDisplay && hoursDisplay !== "00h 00m" && (
                  <div className="truncate text-xs text-slate-400">{hoursDisplay}</div>
                )}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
