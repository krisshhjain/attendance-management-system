import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Box, Button, ButtonGroup, Skeleton, Paper, Tooltip, Typography } from "@mui/material";
import { ChevronLeft, ChevronRight, AccessTime } from "@mui/icons-material";
import { fetchMyShift } from "../../lib/api.js";
import { getHistory } from "../../lib/attendance.js";
import { useActiveHolidays } from "../../data/holidayCalendar.js";

/* ---------- tokens ---------- */
const C = {
  ink: "#1b2a41",
  sub: "#5b6b82",
  faint: "#94a3b8",
  line: "#e6ebf2",
  lineSoft: "#f0f3f8",
  surface: "#ffffff",
  wash: "#f7f9fc",
  brand: "#226db4", // Zoho-style blue
  brandSoft: "#e8f1fb",
  overtime: "#7c5cd6",
};

const STATUS_META = {
  PRESENT: { label: "Present", color: "#1f9d55", bg: "#e6f6ec" },
  COMPLETED: { label: "Present", color: "#1f9d55", bg: "#e6f6ec" },
  INCOMPLETE: { label: "Incomplete", color: "#c2410c", bg: "#fff1e6" },
  CHECKED_IN: { label: "Checked in", color: "#226db4", bg: "#e8f1fb" },
  ABSENT: { label: "Absent", color: "#e11d48", bg: "#ffe9ee" },
  LEAVE: { label: "Leave", color: "#b7791f", bg: "#fff5dc" },
  WEEKEND: { label: "Weekend", color: "#7b8aa0", bg: "#eef2f7" },
  HOLIDAY: { label: "Holiday", color: "#b7791f", bg: "#fff5dc" },
  PENDING: { label: "Not recorded", color: "#7b8aa0", bg: "#eef2f7" },
};
const LIVE_META = { label: "In progress", color: "#226db4", bg: "#e8f1fb" };
const PRESENT_SET = new Set(["PRESENT", "COMPLETED", "INCOMPLETE", "CHECKED_IN"]);

const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/* ---------- helpers (unchanged logic) ---------- */
function dateKey(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function startOfWeek(date) {
  const result = new Date(date);
  const day = result.getDay();
  const mondayOffset = day === 0 ? -6 : 1 - day;
  result.setDate(result.getDate() + mondayOffset);
  result.setHours(0, 0, 0, 0);
  return result;
}

function parseClock(value) {
  const [hours = 0, minutes = 0] = String(value || "00:00").split(":").map(Number);
  return hours * 60 + minutes;
}

function formatClock(minutes) {
  const normalized = ((Math.round(minutes) % 1440) + 1440) % 1440;
  const hours = Math.floor(normalized / 60);
  const mins = normalized % 60;
  return `${String(hours).padStart(2, "0")}:${String(mins).padStart(2, "0")}`;
}

function parseDuration(value) {
  if (typeof value === "number") return value / 60;
  if (!value) return 0;
  if (typeof value === "string" && Number.isFinite(Number(value))) return Number(value) / 60;
  const duration = String(value).match(/^(?:(\d+)\s+days?,\s*)?(\d+):(\d{2}):(\d{2})/);
  if (duration) return (Number(duration[1] || 0) * 1440) + Number(duration[2]) * 60 + Number(duration[3]) + Number(duration[4]) / 60;
  const parts = String(value).split(":").map(Number);
  if (parts.length === 3) return parts[0] * 60 + parts[1] + parts[2] / 60;
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return 0;
}

function parseDurationSeconds(value) {
  return parseDuration(value) * 60;
}

function formatDuration(minutes) {
  const rounded = Math.max(0, Math.round(minutes));
  return `${Math.floor(rounded / 60)}h ${String(rounded % 60).padStart(2, "0")}m`;
}

function timestampMinutes(value, dayKey) {
  if (!value) return null;
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) return null;
  if (dayKey && dateKey(timestamp) !== dayKey) return null;
  return timestamp.getHours() * 60 + timestamp.getMinutes() + timestamp.getSeconds() / 60;
}

function getDayLabel(date) {
  return date.toLocaleDateString("en-US", { month: "short", day: "2-digit" });
}

function getStatus(record, day, todayKey, holiday) {
  const hasActualAttendance = PRESENT_SET.has(record?.status) || record?.status === "LEAVE";
  if (!hasActualAttendance && (day.getDay() === 0 || day.getDay() === 6)) return "WEEKEND";
  if (holiday && !hasActualAttendance) return "HOLIDAY";
  if (record?.status) return record.status;
  if (day.getDay() === 0 || day.getDay() === 6) return "WEEKEND";
  return dateKey(day) < todayKey ? "ABSENT" : "PENDING";
}

/* ---------- layout ---------- */
const GRID = {
  xs: "84px minmax(0, 1fr) 72px",
  md: "128px 60px minmax(320px, 1fr) 60px 104px",
};
const PAD_X = { xs: 1.75, md: 3 };

const cardSx = {
  borderRadius: "14px",
  border: `1px solid ${C.line}`,
  boxShadow: "0 1px 2px rgba(16,24,40,.04), 0 4px 16px rgba(16,24,40,.04)",
  bgcolor: C.surface,
  overflow: "visible",
};

function Stat({ label, value, color }) {
  return (
    <Box sx={{ flex: "1 1 0", minWidth: 96, px: { xs: 1.75, md: 3 }, py: 1.5, borderRight: `1px solid ${C.lineSoft}`, "&:last-of-type": { borderRight: 0 } }}>
      <Typography sx={{ fontSize: 11.5, color: C.sub, fontWeight: 500 }}>{label}</Typography>
      <Typography sx={{ mt: 0.25, fontSize: 19, fontWeight: 700, color: color || C.ink, fontVariantNumeric: "tabular-nums", letterSpacing: "-0.01em" }}>{value}</Typography>
    </Box>
  );
}

function StatusPill({ meta, live }) {
  return (
    <Box sx={{ mt: 0.5, display: "inline-flex", alignItems: "center", gap: 0.6, px: 0.9, height: 20, borderRadius: "10px", bgcolor: meta.bg, color: meta.color, fontSize: 10.5, fontWeight: 600, whiteSpace: "nowrap" }}>
      {live && (
        <Box sx={{ width: 6, height: 6, borderRadius: "50%", bgcolor: meta.color, animation: "wkPulse 1.8s ease-out infinite", "@keyframes wkPulse": { "0%": { boxShadow: `0 0 0 0 ${meta.color}66` }, "100%": { boxShadow: `0 0 0 6px ${meta.color}00` } }, "@media (prefers-reduced-motion: reduce)": { animation: "none" } }} />
      )}
      {meta.label}
    </Box>
  );
}

export function WeeklyAttendanceTrack({ todayData }) {
  const [weekOffset, setWeekOffset] = useState(0);
  const [now, setNow] = useState(() => new Date());
  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ["attendanceHistory"],
    queryFn: getHistory,
  });
  const { data: shiftData, isLoading: shiftLoading } = useQuery({
    queryKey: ["myShift"],
    queryFn: fetchMyShift,
  });
  const { data: activeHolidays = [], isLoading: holidaysLoading, isError: holidaysError } = useActiveHolidays();
  const holidayByDate = useMemo(() => new Map(activeHolidays.map((holiday) => [holiday.date, holiday])), [activeHolidays]);

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const shift = shiftData?.shift;
  const weekStart = useMemo(() => {
    const start = startOfWeek(new Date());
    start.setDate(start.getDate() + weekOffset * 7);
    return start;
  }, [weekOffset]);

  const todayKey = dateKey(new Date());
  const records = useMemo(() => {
    const map = new Map((Array.isArray(history) ? history : []).map((record) => [record.date, record]));
    if (todayData) map.set(todayKey, { ...map.get(todayKey), ...todayData, date: todayKey });
    return map;
  }, [history, todayData, todayKey]);

  const days = useMemo(() => {
    return DAY_NAMES.map((dayName, index) => {
      const day = new Date(weekStart);
      day.setDate(weekStart.getDate() + index);
      const key = dateKey(day);
      const record = records.get(key);
      const holiday = holidayByDate.get(key);
      return { day, dayName, key, record, holiday, status: getStatus(record, day, todayKey, holiday) };
    });
  }, [holidayByDate, records, todayKey, weekStart]);

  if (historyLoading || shiftLoading || holidaysLoading) {
    return (
      <Paper sx={{ ...cardSx, p: 3 }}>
        <Skeleton variant="text" width={160} height={26} />
        <Skeleton variant="text" width={260} height={18} sx={{ mb: 2 }} />
        {[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} variant="rounded" height={44} sx={{ mb: 1.25, borderRadius: "10px" }} />)}
      </Paper>
    );
  }
  if (holidaysError) return <Paper sx={{ ...cardSx, p: 2 }}><Alert severity="warning">Holiday data could not be loaded. Attendance statuses are hidden until it is available.</Alert></Paper>;

  if (!shift) {
    return (
      <Paper sx={{ ...cardSx, p: 3, display: "flex", alignItems: "center", gap: 2 }}>
        <Box sx={{ width: 40, height: 40, borderRadius: "10px", bgcolor: C.brandSoft, color: C.brand, display: "grid", placeItems: "center" }}><AccessTime fontSize="small" /></Box>
        <Box>
          <Typography sx={{ fontSize: 15, fontWeight: 700, color: C.ink }}>Weekly attendance</Typography>
          <Typography sx={{ fontSize: 13, color: C.sub, mt: 0.25 }}>Assign a shift to see attendance against scheduled hours.</Typography>
        </Box>
      </Paper>
    );
  }

  /* ---------- timeline scale ---------- */
  const shiftStart = parseClock(shift.start_time);
  let shiftEnd = parseClock(shift.end_time);
  if (shiftEnd <= shiftStart) shiftEnd += 1440;
  const nowMinutes = now.getHours() * 60 + now.getMinutes() + now.getSeconds() / 60;
  const observedEnds = days
    .map(({ record, key }) => timestampMinutes(record?.check_out, key))
    .filter((value) => value !== null);
  const todayIsOpen = todayData?.status === "CHECKED_IN" || Boolean(todayData?.active_check_in);
  if (todayIsOpen) observedEnds.push(nowMinutes);
  const observedEnd = observedEnds.length ? Math.max(...observedEnds) : shiftEnd;
  const timelineEnd = Math.max(shiftEnd, observedEnd);
  const timelinePadding = timelineEnd > shiftEnd ? Math.min(30, Math.max(10, (timelineEnd - shiftEnd) * 0.15)) : 0;
  const timelineScaleEnd = timelineEnd + timelinePadding;
  const timelineLength = timelineScaleEnd - shiftStart;
  const scaleRatios = [0, 0.25, 0.5, 0.75, 1];
  const scaleLabels = scaleRatios.map((ratio) => formatClock(shiftStart + timelineLength * ratio));
  const shiftPct = ((shiftEnd - shiftStart) / timelineLength) * 100;
  const scheduledMinutes = shiftEnd - shiftStart;
  const periodLabel = `${getDayLabel(weekStart)} – ${getDayLabel(days[6].day)}, ${days[6].day.getFullYear()}`;
  const pct = (minutes) => Math.max(0, Math.min(100, ((minutes - shiftStart) / timelineLength) * 100));

  /* ---------- per-row data ---------- */
  const rows = days.map(({ day, dayName, key, record, status }) => {
    const isToday = key === todayKey;
    const checkIn = timestampMinutes(record?.check_in, isToday ? null : key);
    const checkOut = timestampMinutes(record?.check_out, key);
    const isOpen = record?.status === "INCOMPLETE" || Boolean(record?.active_check_in);
    const isLive = isToday && isOpen;
    const endMinutes = checkOut ?? (isLive ? nowMinutes : null);
    const startPosition = checkIn === null ? 0 : pct(checkIn);
    const endPosition = endMinutes === null ? 0 : Math.max(startPosition, pct(endMinutes));
    const activeCheckIn = isLive ? new Date(record.active_check_in || record.check_in) : null;
    const duration = activeCheckIn && !Number.isNaN(activeCheckIn.getTime())
      ? parseDurationSeconds(record.completed_working_duration) / 60 + Math.max(0, (now.getTime() - activeCheckIn.getTime()) / 60000)
      : parseDuration(record?.working_duration);
    const meta = isLive ? LIVE_META : STATUS_META[status] || STATUS_META.PENDING;
    return { day, dayName, key, record, status, isToday, checkIn, checkOut, isLive, endPosition, startPosition, hasBar: checkIn !== null && endMinutes !== null, duration, meta };
  });

  const workedRows = rows.filter((r) => PRESENT_SET.has(r.status) || r.duration > 0);
  const totalMinutes = workedRows.reduce((sum, r) => sum + r.duration, 0);
  const summary = {
    present: rows.filter((r) => PRESENT_SET.has(r.status)).length,
    absent: rows.filter((r) => r.status === "ABSENT").length,
    leave: rows.filter((r) => r.status === "LEAVE").length,
    avg: workedRows.length ? totalMinutes / workedRows.length : 0,
  };

  return (
    <Paper sx={cardSx}>
      {/* header */}
      <Box sx={{ px: PAD_X, py: 2, display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 1.5 }}>
        <Box>
          <Typography sx={{ fontSize: 16, fontWeight: 700, color: C.ink, letterSpacing: "-0.01em" }}>Weekly attendance</Typography>
          <Box sx={{ mt: 0.5, display: "flex", alignItems: "center", flexWrap: "wrap", gap: 1 }}>
            <Typography sx={{ fontSize: 12.5, color: C.sub }}>{periodLabel}</Typography>
            <Box sx={{ display: "inline-flex", alignItems: "center", gap: 0.6, px: 1, height: 22, borderRadius: "11px", bgcolor: C.brandSoft, color: C.brand, fontSize: 11.5, fontWeight: 600 }}>
              <AccessTime sx={{ fontSize: 13 }} />
              {shift.name} · {shift.start_time} – {shift.end_time}
            </Box>
          </Box>
        </Box>
        <ButtonGroup size="small" variant="outlined" sx={{ "& .MuiButton-root": { borderColor: C.line, color: C.sub, height: 32, "&:hover": { borderColor: C.line, bgcolor: C.wash } } }}>
          <Button aria-label="Previous week" onClick={() => setWeekOffset((v) => v - 1)} sx={{ px: 0.75 }}><ChevronLeft fontSize="small" /></Button>
          <Button onClick={() => setWeekOffset(0)} disabled={weekOffset === 0} sx={{ textTransform: "none", fontWeight: 600, px: 1.75, "&.Mui-disabled": { color: C.ink, bgcolor: C.wash, borderColor: C.line } }}>This week</Button>
          <Button aria-label="Next week" onClick={() => setWeekOffset((v) => v + 1)} sx={{ px: 0.75 }}><ChevronRight fontSize="small" /></Button>
        </ButtonGroup>
      </Box>

      {/* summary strip */}
      <Box sx={{ display: "flex", flexWrap: "wrap", borderTop: `1px solid ${C.line}`, borderBottom: `1px solid ${C.line}`, bgcolor: C.wash }}>
        <Stat label="Total worked" value={formatDuration(totalMinutes)} />
        <Stat label="Daily average" value={formatDuration(summary.avg)} />
        <Stat label="Days present" value={summary.present} color="#1f9d55" />
        <Stat label="Absent" value={summary.absent} color={summary.absent ? "#e11d48" : C.faint} />
        <Stat label="Leave" value={summary.leave} color={summary.leave ? "#b7791f" : C.faint} />
      </Box>

      <Box sx={{ overflow: "visible" }}>
        {/* column header */}
        <Box sx={{ minWidth: { md: 700 }, display: { xs: "none", md: "grid" }, gridTemplateColumns: GRID.md, px: PAD_X, py: 1, color: C.faint, fontSize: 11.5, fontWeight: 600, borderBottom: `1px solid ${C.lineSoft}` }}>
          <span>Day</span>
          <span>Check in</span>
          <Box sx={{ display: "flex", justifyContent: "space-between", fontVariantNumeric: "tabular-nums", px: 0.5 }}>{scaleLabels.map((label, i) => <span key={i}>{label}</span>)}</Box>
          <Box component="span" sx={{ pl: 1.5 }}>Check out</Box>
          <Box component="span" sx={{ textAlign: "right" }}>Hours</Box>
        </Box>

        {rows.map(({ day, dayName, key, record, status, holiday, isToday, checkIn, checkOut, isLive, startPosition, endPosition, hasBar, duration, meta }) => {
          const isWeekend = day.getDay() === 0 || day.getDay() === 6;
          const isAbsent = status === "ABSENT";
          const barColor = isLive ? C.brand : meta.color;
          const overtimeFrom = Math.max(startPosition, shiftPct);
          const hasOvertime = hasBar && endPosition > shiftPct + 0.4;
          const regularEnd = Math.min(endPosition, shiftPct);
          const progress = scheduledMinutes ? Math.min(100, (duration / scheduledMinutes) * 100) : 0;
          const tip = hasBar
            ? `${formatClock(checkIn)} → ${checkOut === null ? "now" : formatClock(checkOut)} · ${formatDuration(duration)} worked`
            : meta.label;

          return (
            <Box
              key={key}
              sx={{
                minWidth: { md: 700 },
                display: "grid",
                gridTemplateColumns: GRID,
                alignItems: "stretch",
                minHeight: isWeekend ? 56 : 72,
                px: PAD_X,
                borderBottom: `1px solid ${C.lineSoft}`,
                bgcolor: isToday ? "#f4f8fd" : "transparent",
                boxShadow: isToday ? `inset 3px 0 0 ${C.brand}` : "none",
                opacity: isWeekend ? 0.75 : 1,
                transition: "background-color .15s",
                "&:hover": { bgcolor: isToday ? "#eef4fc" : C.wash },
              }}
            >
              {/* day */}
              <Box sx={{ alignSelf: "center", py: 1 }}>
                <Box sx={{ display: "flex", alignItems: "baseline", gap: 0.75 }}>
                  <Typography sx={{ fontSize: 13, fontWeight: 700, color: isToday ? C.brand : C.ink }}>{dayName}</Typography>
                  <Typography sx={{ fontSize: 11.5, color: C.sub }}>{getDayLabel(day)}</Typography>
                </Box>
                <StatusPill meta={meta} live={isLive} />
                {holiday && <Typography title={holiday.name} sx={{ mt: 0.25, fontSize: 10, color: C.sub }}>{holiday.name}</Typography>}
              </Box>

              {/* check in (desktop) */}
              <Typography sx={{ alignSelf: "center", display: { xs: "none", md: "block" }, fontSize: 12.5, color: checkIn === null ? C.faint : C.ink, fontWeight: 500, fontVariantNumeric: "tabular-nums" }}>
                {checkIn === null ? "--:--" : formatClock(checkIn)}
              </Typography>

              {/* timeline */}
              <Tooltip title={tip} placement="top" arrow disableInteractive>
                <Box sx={{
                  gridColumn: { xs: "2", md: "3" },
                  position: "relative",
                  mx: { xs: 1.5, md: 0.5 },
                  alignSelf: "center",
                  height: isWeekend ? 1 : 40,
                  minHeight: 0,
                  overflow: "visible",
                  ...(isWeekend ? { bgcolor: C.line, "& > *": { display: "none" } } : {}),
                }}>
                  {/* gridlines */}
                  {!isWeekend && scaleRatios.map((r) => (
                    <Box key={r} sx={{ position: "absolute", top: 0, bottom: 0, left: `${r * 100}%`, width: "1px", bgcolor: C.lineSoft }} />
                  ))}
                  {/* scheduled window */}
                  {!isWeekend && (
                    <Box sx={{ position: "absolute", left: 0, width: `${shiftPct}%`, top: "50%", height: 22, transform: "translateY(-50%)", borderRadius: "6px", bgcolor: "rgba(34,109,180,.07)", border: "1px dashed rgba(34,109,180,.22)" }} />
                  )}
                  {isWeekend && <Box sx={{ position: "absolute", left: 0, right: 0, top: "50%", height: 1, bgcolor: C.line }} />}
                  {isAbsent && <Box sx={{ position: "absolute", left: 0, width: `${shiftPct}%`, top: "50%", height: 2, borderRadius: 1, backgroundImage: "repeating-linear-gradient(90deg, #f7a1b3 0 6px, transparent 6px 12px)" }} />}

                  {/* worked: regular */}
                  {hasBar && regularEnd > startPosition && (
                    <Box sx={{ position: "absolute", left: `${startPosition}%`, width: `${regularEnd - startPosition}%`, top: "50%", height: 10, transform: "translateY(-50%)", borderRadius: hasOvertime ? "5px 0 0 5px" : "5px", background: isLive ? `linear-gradient(90deg, ${C.brand} 0%, #6aa6e0 50%, ${C.brand} 100%)` : barColor, backgroundSize: isLive ? "200% 100%" : "auto", animation: isLive ? "wkFlow 2.4s linear infinite" : "none", "@keyframes wkFlow": { from: { backgroundPosition: "0% 0" }, to: { backgroundPosition: "200% 0" } }, "@media (prefers-reduced-motion: reduce)": { animation: "none" } }} />
                  )}
                  {/* worked: beyond shift end */}
                  {hasOvertime && (
                    <Box sx={{ position: "absolute", left: `${overtimeFrom}%`, width: `${endPosition - overtimeFrom}%`, top: "50%", height: 10, transform: "translateY(-50%)", borderRadius: overtimeFrom > startPosition ? "0 5px 5px 0" : "5px", bgcolor: C.overtime }} />
                  )}
                  {/* in / out caps */}
                  {hasBar && (
                    <Box sx={{ position: "absolute", left: `${startPosition}%`, top: "50%", width: 14, height: 14, transform: "translate(-50%, -50%)", borderRadius: "50%", bgcolor: "#fff", border: `3px solid ${barColor}` }} />
                  )}
                  {hasBar && !isLive && (
                    <Box sx={{ position: "absolute", left: `${endPosition}%`, top: "50%", width: 14, height: 14, transform: "translate(-50%, -50%)", borderRadius: "50%", bgcolor: hasOvertime ? C.overtime : barColor, border: "3px solid #fff", boxShadow: `0 0 0 1px ${hasOvertime ? C.overtime : barColor}` }} />
                  )}
                  {isLive && hasBar && (
                    <Box sx={{ position: "absolute", left: `${endPosition}%`, top: "50%", transform: "translate(-50%, -50%)", width: 14, height: 14, borderRadius: "50%", bgcolor: C.brand, border: "3px solid #fff", boxShadow: `0 0 0 1px ${C.brand}` }}>
                      <Box sx={{ position: "absolute", top: -22, left: "50%", transform: "translateX(-50%)", px: 0.75, borderRadius: "4px", bgcolor: C.brand, color: "#fff", fontSize: 9.5, fontWeight: 700, lineHeight: "15px" }}>Live</Box>
                    </Box>
                  )}
                  {/* single check-in with no bar yet */}
                  {!hasBar && checkIn !== null && (
                    <Box sx={{ position: "absolute", left: `${startPosition}%`, top: "50%", width: 14, height: 14, transform: "translate(-50%, -50%)", borderRadius: "50%", bgcolor: "#fff", border: `3px solid ${meta.color}` }} />
                  )}
                </Box>
              </Tooltip>

              {/* check out (desktop) */}
              <Typography sx={{ alignSelf: "center", pl: 1.5, display: { xs: "none", md: "block" }, fontSize: 12.5, color: checkOut === null && !isLive ? C.faint : isLive ? C.brand : C.ink, fontWeight: 500, fontVariantNumeric: "tabular-nums" }}>
                {checkOut === null ? (isLive ? "Now" : "--:--") : formatClock(checkOut)}
              </Typography>

              {/* hours */}
              <Box sx={{ alignSelf: "center", textAlign: "right" }}>
                <Typography sx={{ fontSize: 13, fontWeight: 700, color: duration > 0 ? C.ink : C.faint, fontVariantNumeric: "tabular-nums" }}>{duration > 0 ? formatDuration(duration) : "–"}</Typography>
                {!isWeekend && (
                  <Box sx={{ mt: 0.75, ml: "auto", width: { xs: 48, md: 64 }, height: 4, borderRadius: 2, bgcolor: C.lineSoft, overflow: "hidden" }}>
                    <Box sx={{ width: `${progress}%`, height: "100%", borderRadius: 2, bgcolor: progress >= 100 ? "#1f9d55" : isLive ? C.brand : "#f0a640", transition: "width .4s ease" }} />
                  </Box>
                )}
              </Box>
            </Box>
          );
        })}
      </Box>

      {/* legend */}
      <Box sx={{ display: "flex", gap: { xs: 1.75, md: 2.5 }, flexWrap: "wrap", alignItems: "center", px: PAD_X, py: 1.5, bgcolor: C.wash, color: C.sub, fontSize: 11.5 }}>
        {[["#1f9d55", "Present"], [C.brand, "In progress"], [C.overtime, "Beyond shift end"], ["#e11d48", "Absent"], ["#b7791f", "Leave"]].map(([color, label]) => (
          <Box key={label} sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
            <Box sx={{ width: 14, height: 6, borderRadius: 3, bgcolor: color }} />
            {label}
          </Box>
        ))}
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
          <Box sx={{ width: 14, height: 10, borderRadius: "3px", bgcolor: "rgba(34,109,180,.07)", border: "1px dashed rgba(34,109,180,.35)" }} />
          Scheduled shift
        </Box>
      </Box>
    </Paper>
  );
}
