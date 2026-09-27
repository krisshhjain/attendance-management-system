import React from "react";
import type { AttendanceRecord } from "../../types";
import { isToday } from "../../utils/dateUtils";

interface MobileTimelineEntry {
  dayName: string;
  dateDisplay: string;
  record: AttendanceRecord;
}

export default function MobileAttendanceTimeline({
  entries,
  selectedDate,
  onSelectRecord,
  statusDot,
  filterMatch,
}: {
  entries: MobileTimelineEntry[];
  selectedDate?: string;
  onSelectRecord: (record: AttendanceRecord) => void;
  statusDot: Record<string, string>;
  filterMatch: (status: string) => boolean;
}) {
  return (
    <div className="w-full min-w-0 overflow-hidden md:hidden divide-y divide-slate-100">
      {entries.map(({ dayName, dateDisplay, record }) => {
        const { date, status, checkIn, checkOut, workingHours } = record;
        const isCurrentDay = isToday(date);
        const weekend = status === "Weekend";
        const issue = status === "Missing Check-out";
        const selected = selectedDate === date;

        const lineColor =
          status === "Work From Home"
            ? "bg-violet-500"
            : status === "On Duty"
            ? "bg-blue-500"
            : status === "On Leave"
            ? "bg-amber-500"
            : status === "Absent"
            ? "bg-rose-500"
            : issue
            ? "bg-orange-500"
            : "bg-emerald-500";

        const matchesFilter = filterMatch(status);

        return (
          <button
            key={`mobile-${date}`}
            type="button"
            aria-label={`View attendance for ${dayName}, ${dateDisplay}`}
            onClick={() => onSelectRecord(record)}
            className={`min-h-20 w-full min-w-0 text-left p-4 hover:bg-slate-50 transition ${
              isCurrentDay ? "bg-indigo-50/60 ring-1 ring-inset ring-indigo-200" : ""
            } ${selected ? "ring-2 ring-inset ring-blue-500" : ""} ${
              matchesFilter ? "opacity-100" : "opacity-30"
            }`}
          >
            <div className="flex min-w-0 items-start justify-between gap-3">
              <div className="flex min-w-0 items-center gap-2">
                <span className="type-caption font-semibold tracking-wider text-slate-700">
                  {dayName}
                </span>
                <span className="type-meta text-slate-500">{dateDisplay}</span>
                {isCurrentDay && (
                  <span className="type-caption rounded-full bg-indigo-100 px-1.5 py-0.5 font-semibold text-indigo-700">
                    Today
                  </span>
                )}
              </div>
              <span className="shrink-0 text-xs font-semibold text-slate-800">
                {weekend ? "00h 00m" : workingHours}
              </span>
            </div>

            {weekend ? (
              <div className="mt-3 flex min-w-0 items-center gap-3">
                <span className="h-px min-w-0 flex-1 bg-slate-200" />
                <span className="type-meta shrink-0 font-medium text-slate-400">Weekend</span>
                <span className="h-px min-w-0 flex-1 bg-slate-200" />
              </div>
            ) : (
              <>
                <div className="mt-3 flex min-w-0 items-center gap-2">
                  <span className="type-caption shrink-0 font-medium text-slate-700">
                    {checkIn}
                  </span>
                  <span className="flex min-w-0 flex-1 items-center">
                    <span className={`size-2.5 shrink-0 rounded-full ${lineColor}`} />
                    <span className={`h-0.5 min-w-0 flex-1 ${lineColor}`} />
                    {issue ? (
                      <span className="shrink-0 font-bold text-orange-600">!</span>
                    ) : (
                      <span className={`size-2.5 shrink-0 rounded-full ${lineColor}`} />
                    )}
                  </span>
                  <span
                    className={`type-caption shrink-0 font-medium ${
                      issue ? "text-orange-700" : "text-slate-700"
                    }`}
                  >
                    {issue ? "Not recorded" : checkOut}
                  </span>
                </div>
                <div
                  className={`type-meta mt-2 flex items-center gap-1.5 font-medium ${
                    issue ? "text-orange-700" : "text-slate-600"
                  }`}
                >
                  {issue ? (
                    <span className="text-orange-600 font-bold">!</span>
                  ) : (
                    <span className={`size-2 rounded-full ${statusDot[status] || "bg-slate-400"}`} />
                  )}
                  {status}
                </div>
              </>
            )}
          </button>
        );
      })}
    </div>
  );
}
