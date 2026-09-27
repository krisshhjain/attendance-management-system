import React, { useState, useMemo } from "react";
import Card from "../common/Card";
import Button from "../common/Button";
import SectionTitle from "../common/SectionTitle";
import CompactMonth from "./CompactMonth";
import CompactYear from "./CompactYear";
import MobileAttendanceTimeline from "./MobileAttendanceTimeline";
import AttendanceDetailModal from "./AttendanceDetailModal";
import { useApp } from "../../context/AppContext";
import type { AttendanceRecord, Page } from "../../types";
import {
  getWeekDates,
  formatToISODate,
  formatDateDisplay,
  isToday,
  calculateTimelinePosition,
  MONTH_NAMES_SHORT,
  MONTH_NAMES_FULL,
} from "../../utils/dateUtils";

const statusDot: Record<string, string> = {
  Present: "bg-emerald-500",
  Absent: "bg-rose-500",
  "On Leave": "bg-amber-500",
  "Work From Home": "bg-violet-500",
  "On Duty": "bg-blue-500",
  Weekend: "bg-slate-300",
  "Missing Check-out": "bg-orange-500",
  Pending: "bg-slate-300",
};

export default function WeeklyAttendance({
  onRegularize,
}: {
  onRegularize: (dateIso: string, checkIn?: string) => void;
}) {
  const { attendanceRecords, setActivePage } = useApp();
  const [view, setView] = useState<"Week" | "Month" | "Year">("Week");
  const [weekOffset, setWeekOffset] = useState(0);

  const now = new Date();
  const [selectedMonth, setSelectedMonth] = useState(now.getMonth());
  const [selectedYear, setSelectedYear] = useState(now.getFullYear());
  const [filter, setFilter] = useState("All");
  const [selectedRecord, setSelectedRecord] = useState<AttendanceRecord | null>(null);

  // Compute 7 days for the selected week
  const weekDates = useMemo(() => {
    return getWeekDates(new Date(), weekOffset);
  }, [weekOffset]);

  const weekEntries = useMemo(() => {
    const dayNames = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];
    return weekDates.map((dateObj, index) => {
      const iso = formatToISODate(dateObj);
      const day = String(dateObj.getDate()).padStart(2, "0");
      const month = MONTH_NAMES_SHORT[dateObj.getMonth()];
      const dayName = dayNames[index];
      const dateDisplay = `${day} ${month}`;

      const todayIso = formatToISODate(new Date());
      const isPast = iso < todayIso;
      const isWeekendDay = index === 5 || index === 6;

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

      return {
        dayName,
        dateDisplay,
        dateObj,
        record,
      };
    });
  }, [weekDates, attendanceRecords]);

  // Dynamic period label
  const periodLabel = useMemo(() => {
    if (view === "Week") {
      const start = weekDates[0];
      const end = weekDates[6];
      const startMonth = MONTH_NAMES_SHORT[start.getMonth()];
      const endMonth = MONTH_NAMES_SHORT[end.getMonth()];
      const startYear = start.getFullYear();
      const endYear = end.getFullYear();

      if (startMonth === endMonth && startYear === endYear) {
        return `${start.getDate()} – ${end.getDate()} ${startMonth} ${startYear}`;
      }
      return `${start.getDate()} ${startMonth} – ${end.getDate()} ${endMonth} ${endYear}`;
    }
    if (view === "Month") {
      return `${MONTH_NAMES_FULL[selectedMonth]} ${selectedYear}`;
    }
    return `${selectedYear}`;
  }, [view, weekDates, selectedMonth, selectedYear]);

  // Week navigation
  const movePeriod = (direction: number) => {
    if (view === "Week") {
      setWeekOffset((prev) => prev + direction);
    } else if (view === "Month") {
      let newMonth = selectedMonth + direction;
      let newYear = selectedYear;
      if (newMonth < 0) {
        newMonth = 11;
        newYear -= 1;
      } else if (newMonth > 11) {
        newMonth = 0;
        newYear += 1;
      }
      setSelectedMonth(newMonth);
      setSelectedYear(newYear);
    } else {
      setSelectedYear((prev) => prev + direction);
    }
  };

  const resetPeriod = () => {
    const cur = new Date();
    setWeekOffset(0);
    setSelectedMonth(cur.getMonth());
    setSelectedYear(cur.getFullYear());
  };

  // Filter matching
  const filterMatch = (status: string) => {
    if (filter === "All") return true;
    if (filter === "Leave" && status === "On Leave") return true;
    return status === filter;
  };

  // Weekly summary counts
  const weekSummary = useMemo(() => {
    let present = 0;
    let wfh = 0;
    let leave = 0;
    let onDuty = 0;
    let totalMinutes = 0;
    let issueRecord: AttendanceRecord | null = null;

    weekEntries.forEach(({ record }) => {
      if (record.status === "Present") present++;
      else if (record.status === "Work From Home") wfh++;
      else if (record.status === "On Leave") leave++;
      else if (record.status === "On Duty") onDuty++;

      if (record.status === "Missing Check-out" && !issueRecord) {
        issueRecord = record;
      }

      if (record.workingMinutes) {
        totalMinutes += record.workingMinutes;
      }
    });

    const hours = Math.floor(totalMinutes / 60);
    const mins = totalMinutes % 60;
    const formattedHours = `${String(hours).padStart(2, "0")}h ${String(mins).padStart(2, "0")}m`;

    return {
      present,
      wfh,
      leave,
      onDuty,
      formattedHours,
      issueRecord,
    };
  }, [weekEntries]);

  return (
    <Card className="overflow-hidden">
      <SectionTitle
        title="Weekly Attendance"
        subtitle={periodLabel}
        action={
          <div className="flex flex-wrap items-center gap-1">
            <Button
              variant="secondary"
              className="min-h-8 px-2"
              onClick={() => movePeriod(-1)}
              ariaLabel="Previous period"
            >
              ←
            </Button>
            <Button variant="secondary" className="min-h-8 px-3" onClick={resetPeriod}>
              {view === "Week" ? "This Week" : view === "Month" ? "This Month" : "This Year"}
            </Button>
            <Button
              variant="secondary"
              className="min-h-8 px-2"
              onClick={() => movePeriod(1)}
              ariaLabel="Next period"
            >
              →
            </Button>
          </div>
        }
      />

      <div className="flex gap-1 border-b border-slate-200 bg-slate-50 px-4 py-2">
        {(["Week", "Month", "Year"] as const).map((item) => (
          <Button
            key={item}
            variant="ghost"
            className={`min-h-8 px-3 text-xs ${
              view === item ? "bg-white text-indigo-700 shadow-sm font-semibold" : "text-slate-500"
            }`}
            onClick={() => setView(item)}
          >
            {item}
          </Button>
        ))}
      </div>

      {view === "Week" && (
        <div>
          {/* Desktop Timeline */}
          <div className="hidden w-full min-w-0 md:block">
            <div className="w-full min-w-0">
              <div className="flex items-end border-b border-slate-200 bg-slate-50 px-4 py-2">
                <div className="type-caption w-20 shrink-0 font-medium text-slate-400">Day</div>
                <div className="type-caption w-24 shrink-0 font-medium text-slate-400">Check-in</div>
                <div className="min-w-0 flex-1">
                  <div className="type-caption flex justify-between font-normal text-slate-400">
                    {[
                      "09:00",
                      "10:00",
                      "11:00",
                      "12:00",
                      "01:00",
                      "02:00",
                      "03:00",
                      "04:00",
                      "05:00",
                      "06:00",
                    ].map((time, idx) => (
                      <span key={time} className={idx % 2 && idx !== 9 ? "hidden lg:inline" : ""}>
                        {time}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="type-caption w-24 shrink-0 text-right font-medium text-slate-400">
                  Check-out
                </div>
                <div className="type-caption w-24 shrink-0 text-right font-medium text-slate-400">
                  Hours
                </div>
              </div>

              {weekEntries.map(({ dayName, dateDisplay, record }) => {
                const { date, status, checkIn, checkOut, workingHours } = record;
                const isCurrentDay = isToday(date);
                const weekend = status === "Weekend";
                const isIssue = status === "Missing Check-out";
                const selected = selectedRecord?.date === date;

                const start = calculateTimelinePosition(checkIn);
                const finish =
                  checkOut === "--:--"
                    ? Math.max(start + 10, 76)
                    : calculateTimelinePosition(checkOut);

                const lineColor =
                  status === "Work From Home"
                    ? "bg-violet-500"
                    : status === "On Duty"
                    ? "bg-blue-500"
                    : status === "On Leave"
                    ? "bg-amber-500"
                    : status === "Absent"
                    ? "bg-rose-500"
                    : isIssue
                    ? "bg-orange-500"
                    : "bg-emerald-500";

                return (
                  <button
                    key={`week-${date}`}
                    type="button"
                    aria-label={`View attendance for ${dayName}, ${dateDisplay}`}
                    onClick={() => setSelectedRecord(record)}
                    className={`relative flex w-full items-center border-b border-slate-100 px-4 py-3 text-left hover:bg-slate-50 transition outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${
                      isCurrentDay ? "bg-indigo-50/60 ring-1 ring-inset ring-indigo-200" : ""
                    } ${selected ? "bg-blue-50 ring-2 ring-inset ring-blue-500" : ""} ${
                      filterMatch(status) ? "opacity-100" : "opacity-30"
                    }`}
                  >
                    <div className="w-20 shrink-0">
                      <div className="flex items-center gap-1.5">
                        <span className="type-caption font-semibold tracking-wider text-slate-700">
                          {dayName}
                        </span>
                        {isCurrentDay && <span className="size-2 rounded-full bg-indigo-500" />}
                      </div>
                      <div className="type-meta mt-0.5 font-normal text-slate-500">
                        {dateDisplay}
                      </div>
                      {isCurrentDay && (
                        <div className="type-caption mt-1 font-semibold text-indigo-600">Today</div>
                      )}
                    </div>

                    <div className="type-caption w-24 shrink-0 font-medium text-slate-700">
                      {weekend ? "—" : checkIn}
                    </div>

                    <div className="relative h-12 min-w-0 flex-1">
                      {weekend ? (
                        <div className="absolute inset-x-0 top-4 flex items-center gap-3">
                          <span className="h-px flex-1 bg-slate-200" />
                          <span className="type-meta font-medium text-slate-400">Weekend</span>
                          <span className="h-px flex-1 bg-slate-200" />
                        </div>
                      ) : (
                        <>
                          <span className="absolute inset-x-0 top-4 h-px bg-slate-200" />
                          <span
                            className={`absolute top-3.5 h-1 rounded-full ${lineColor}`}
                            style={{
                              left: `${start}%`,
                              width: `${Math.max(2, finish - start)}%`,
                            }}
                          />
                          <span
                            className={`absolute top-2.5 size-3 -translate-x-1/2 rounded-full border-2 border-white shadow-sm ${lineColor}`}
                            style={{ left: `${start}%` }}
                          />
                          {isIssue ? (
                            <span
                              className="absolute top-1 -translate-x-1/2 text-sm font-bold text-orange-600"
                              style={{ left: `${finish}%` }}
                            >
                              !
                            </span>
                          ) : (
                            checkOut !== "--:--" && (
                              <span
                                className={`absolute top-2.5 size-3 -translate-x-1/2 rounded-full border-2 border-white shadow-sm ${lineColor}`}
                                style={{ left: `${finish}%` }}
                              />
                            )
                          )}
                          <div
                            className={`type-meta absolute bottom-0 left-0 flex items-center gap-1.5 font-medium ${
                              isIssue ? "text-orange-700" : "text-slate-600"
                            }`}
                          >
                            {isIssue ? (
                              <span className="text-orange-600 font-bold">!</span>
                            ) : (
                              <span
                                className={`size-2 rounded-full ${statusDot[status] || "bg-slate-400"}`}
                              />
                            )}
                            {status}
                          </div>
                        </>
                      )}
                    </div>

                    <div className="type-caption w-24 shrink-0 text-right font-medium text-slate-700">
                      {weekend ? "—" : checkOut === "--:--" ? "Not recorded" : checkOut}
                    </div>

                    <div className="w-24 shrink-0 text-right">
                      <div className="text-xs font-semibold text-slate-800">
                        {weekend ? "00h 00m" : workingHours}
                      </div>
                      <div className="type-caption font-normal text-slate-400">Hrs worked</div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Mobile Timeline */}
          <MobileAttendanceTimeline
            entries={weekEntries}
            selectedDate={selectedRecord?.date}
            onSelectRecord={setSelectedRecord}
            statusDot={statusDot}
            filterMatch={filterMatch}
          />

          {/* Filter Pills */}
          <div className="flex flex-wrap items-center gap-2 border-t border-slate-200 px-4 py-3">
            {[
              "All",
              "Present",
              "Absent",
              "Leave",
              "Work From Home",
              "On Duty",
              "Weekend",
            ].map((item) => (
              <Button
                key={item}
                variant="ghost"
                className={`min-h-8 px-2.5 text-xs ${
                  filter === item ? "bg-indigo-50 text-indigo-700 font-semibold" : "text-slate-500"
                }`}
                onClick={() => setFilter(item)}
              >
                {item !== "All" && (
                  <span
                    className={`size-2 rounded-full ${
                      statusDot[item === "Leave" ? "On Leave" : item] || "bg-slate-400"
                    }`}
                  />
                )}
                {item}
              </Button>
            ))}
          </div>

          {/* Weekly Summary Bar */}
          <div className="border-t border-slate-200 bg-slate-50 px-4 py-3">
            <div className="mb-2 text-xs font-bold text-slate-700">
              {weekOffset === 0 ? "This Week" : "Week Summary"}
            </div>
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs text-slate-500">
              <span>
                <strong className="text-slate-800">{weekSummary.present} Days</strong> Present
              </span>
              <span>
                <strong className="text-slate-800">{weekSummary.wfh} Day</strong> Work From Home
              </span>
              <span>
                <strong className="text-slate-800">{weekSummary.leave} Days</strong> Leave
              </span>
              <span>
                <strong className="text-slate-800">{weekSummary.onDuty} Days</strong> On Duty
              </span>
              <span>
                <strong className="text-slate-800">{weekSummary.formattedHours}</strong> Total Hours
              </span>

              {weekSummary.issueRecord && (
                <Button
                  variant="ghost"
                  className="ml-auto min-h-8 justify-start px-2 text-orange-700 hover:text-orange-800 font-semibold"
                  onClick={() => setSelectedRecord(weekSummary.issueRecord)}
                >
                  ! 1 attendance record requires attention
                </Button>
              )}
            </div>
          </div>
        </div>
      )}

      {view === "Month" && (
        <CompactMonth
          year={selectedYear}
          month={selectedMonth}
          attendanceRecords={attendanceRecords}
          statusDot={statusDot}
          onSelect={setSelectedRecord}
        />
      )}

      {view === "Year" && (
        <CompactYear
          year={selectedYear}
          attendanceRecords={attendanceRecords}
          onSelectMonth={(monthIdx) => {
            setSelectedMonth(monthIdx);
            setView("Month");
          }}
        />
      )}

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
    </Card>
  );
}
