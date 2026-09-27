import React, { useMemo } from "react";
import type { AttendanceRecord } from "../../types";
import { MONTH_NAMES_SHORT } from "../../utils/dateUtils";

export default function CompactYear({
  year,
  attendanceRecords,
  onSelectMonth,
}: {
  year: number;
  attendanceRecords: Record<string, AttendanceRecord>;
  onSelectMonth: (monthIndex: number) => void;
}) {
  const currentMonthIndex = new Date().getMonth();
  const currentYear = new Date().getFullYear();

  // Aggregate monthly counts from actual attendance records
  const monthlyStats = useMemo(() => {
    return MONTH_NAMES_SHORT.map((_, monthIndex) => {
      let presentCount = 0;
      let leaveCount = 0;

      Object.values(attendanceRecords || {}).forEach((record) => {
        const [y, m] = record.date.split("-").map(Number);
        if (y === year && m - 1 === monthIndex) {
          if (
            record.status === "Present" ||
            record.status === "Work From Home" ||
            record.status === "On Duty"
          ) {
            presentCount++;
          } else if (record.status === "On Leave") {
            leaveCount++;
          }
        }
      });

      return {
        present: presentCount,
        leave: leaveCount,
      };
    });
  }, [year, attendanceRecords]);

  return (
    <div className="overflow-x-auto p-3">
      <div className="grid min-w-5xl grid-cols-12 gap-2">
        {MONTH_NAMES_SHORT.map((monthName, index) => {
          const stats = monthlyStats[index];
          const isCurrent = year === currentYear && index === currentMonthIndex;

          return (
            <button
              key={monthName}
              type="button"
              aria-label={`Open ${monthName} ${year} attendance`}
              onClick={() => onSelectMonth(index)}
              className={`rounded-lg border p-2.5 text-left transition hover:border-indigo-300 outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
                isCurrent
                  ? "border-indigo-300 bg-indigo-50/60 ring-1 ring-inset ring-indigo-200"
                  : "border-slate-200 bg-slate-50/70 hover:bg-white"
              }`}
            >
              <div className="text-xs font-bold text-slate-700 flex items-center justify-between">
                <span>{monthName}</span>
                {isCurrent && <span className="size-1.5 rounded-full bg-indigo-600" />}
              </div>

              <div className="mt-2 flex items-center gap-1 text-xs text-slate-500">
                <span className="size-1.5 rounded-full bg-emerald-500 shrink-0" />
                <span>Present</span>
                <span className="ml-auto font-semibold text-slate-700">{stats.present}</span>
              </div>

              <div className="mt-1.5 flex items-center gap-1 text-xs text-slate-500">
                <span className="size-1.5 rounded-full bg-amber-500 shrink-0" />
                <span>Leave</span>
                <span className="ml-auto font-semibold text-slate-700">{stats.leave}</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
