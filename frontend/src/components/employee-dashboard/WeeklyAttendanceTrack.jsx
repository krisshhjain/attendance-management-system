import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Box, Button, Chip, CircularProgress, Paper, Typography } from "@mui/material";
import { ChevronLeft, ChevronRight } from "@mui/icons-material";
import { fetchMyShift } from "../../lib/api.js";
import { getHistory } from "../../lib/attendance.js";

const DAY_NAMES = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"];
const STATUS_COLORS = {
  PRESENT: "#16a34a",
  COMPLETED: "#16a34a",
  INCOMPLETE: "#2563eb",
  CHECKED_IN: "#2563eb",
  ABSENT: "#f43f5e",
  LEAVE: "#f59e0b",
  WEEKEND: "#cbd5e1",
};

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
  const parts = String(value).split(":").map(Number);
  if (parts.length === 3) return parts[0] * 60 + parts[1] + parts[2] / 60;
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return 0;
}

function formatDuration(minutes) {
  const rounded = Math.max(0, Math.round(minutes));
  return `${String(Math.floor(rounded / 60)).padStart(2, "0")}h ${String(rounded % 60).padStart(2, "0")}m`;
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

function getStatus(record, day, todayKey) {
  if (record?.status) return record.status;
  if (day.getDay() === 0 || day.getDay() === 6) return "WEEKEND";
  return dateKey(day) < todayKey ? "ABSENT" : "PENDING";
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
      return { day, dayName, key, record: records.get(key), status: getStatus(records.get(key), day, todayKey) };
    });
  }, [records, todayKey, weekStart]);

  if (historyLoading || shiftLoading) {
    return <Paper sx={{ p: 4, display: "flex", justifyContent: "center", borderRadius: 3, border: "1px solid", borderColor: "divider", boxShadow: "none" }}><CircularProgress size={24} /></Paper>;
  }

  if (!shift) {
    return (
      <Paper sx={{ p: 3, borderRadius: 3, border: "1px solid", borderColor: "divider", boxShadow: "none" }}>
        <Typography variant="h6" sx={{ fontWeight: 700 }}>Weekly Attendance</Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>Assign a shift to see attendance against scheduled hours.</Typography>
      </Paper>
    );
  }

  const shiftStart = parseClock(shift.start_time);
  let shiftEnd = parseClock(shift.end_time);
  if (shiftEnd <= shiftStart) shiftEnd += 1440;
  const observedEnds = days
    .map(({ record, key }) => timestampMinutes(record?.check_out, key))
    .filter((value) => value !== null);
  const todayIsOpen = todayData?.check_in && !todayData?.check_out;
  if (todayIsOpen) {
    observedEnds.push(now.getHours() * 60 + now.getMinutes() + now.getSeconds() / 60);
  }
  const observedEnd = observedEnds.length ? Math.max(...observedEnds) : shiftEnd;
  const timelineEnd = Math.max(shiftEnd, observedEnd);
  const timelinePadding = timelineEnd > shiftEnd ? Math.min(30, Math.max(10, (timelineEnd - shiftEnd) * 0.15)) : 0;
  const timelineScaleEnd = timelineEnd + timelinePadding;
  const timelineLength = timelineScaleEnd - shiftStart;
  const scaleLabels = [0, 0.25, 0.5, 0.75, 1].map((ratio) => formatClock(shiftStart + timelineLength * ratio));
  const periodLabel = `${getDayLabel(weekStart)} - ${getDayLabel(days[6].day)} ${days[6].day.getFullYear()}`;

  return (
    <Paper sx={{ overflow: "visible", height: "auto", borderRadius: 3, border: "1px solid", borderColor: "#dbe3ee", boxShadow: "0 2px 8px rgba(15, 23, 42, 0.06)" }}>
      <Box sx={{ minWidth: { xs: 0, md: 680 }, px: { xs: 2, sm: 2.5 }, py: 1.75, borderBottom: "1px solid", borderColor: "#e5ebf2", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 2 }}>
        <Box>
          <Typography sx={{ fontSize: 15, fontWeight: 700, color: "#1e293b" }}>Weekly Attendance</Typography>
          <Typography sx={{ fontSize: 11, color: "#718096", mt: 0.25 }}>{periodLabel} · {shift.name} ({shift.start_time} - {shift.end_time})</Typography>
        </Box>
        <Box sx={{ display: "flex", gap: 0.75 }}>
          <Button size="small" variant="outlined" onClick={() => setWeekOffset((value) => value - 1)} sx={{ minWidth: 36, px: 0 }}> <ChevronLeft fontSize="small" /> </Button>
          <Button size="small" variant="outlined" onClick={() => setWeekOffset(0)} sx={{ textTransform: "none", minWidth: 82 }}>This Week</Button>
          <Button size="small" variant="outlined" onClick={() => setWeekOffset((value) => value + 1)} sx={{ minWidth: 36, px: 0 }}> <ChevronRight fontSize="small" /> </Button>
        </Box>
      </Box>

      <Box sx={{ minWidth: { xs: 0, md: 680 }, display: { xs: "none", md: "grid" }, gridTemplateColumns: "100px 62px minmax(300px, 1fr) 78px 76px", px: 2.5, py: 1, bgcolor: "#f8fafc", borderBottom: "1px solid #e5ebf2", color: "#718096", fontSize: 10, fontWeight: 700, textTransform: "uppercase" }}>
        <span>Day</span><span>In</span><Box sx={{ display: "flex", justifyContent: "space-between" }}>{scaleLabels.map((label) => <span key={label}>{label}</span>)}</Box><span>Out</span><span>Hours</span>
      </Box>

      {days.map(({ day, dayName, key, record, status }) => {
        const color = STATUS_COLORS[status] || "#cbd5e1";
        const isToday = key === todayKey;
        const checkIn = timestampMinutes(record?.check_in, isToday ? null : key);
        const checkOut = timestampMinutes(record?.check_out, key);
        const isOpen = checkIn !== null && checkOut === null;
        const isLive = isToday && isOpen;
        const endMinutes = checkOut ?? (isLive ? now.getHours() * 60 + now.getMinutes() + now.getSeconds() / 60 : null);
        const startPosition = checkIn === null ? 0 : Math.max(0, Math.min(100, ((checkIn - shiftStart) / timelineLength) * 100));
        const endPosition = endMinutes === null ? (status === "ABSENT" ? 100 : 0) : Math.max(startPosition, Math.min(100, ((endMinutes - shiftStart) / timelineLength) * 100));
        const liveCheckIn = isLive ? new Date(record.check_in) : null;
        const duration = liveCheckIn && !Number.isNaN(liveCheckIn.getTime())
          ? Math.max(0, (now.getTime() - liveCheckIn.getTime()) / 60000)
          : parseDuration(record?.working_duration);
        const isWeekend = status === "WEEKEND";

        return (
          <Box key={key} sx={{ minWidth: { xs: 0, md: 680 }, display: "grid", gridTemplateColumns: { xs: "64px minmax(0, 1fr) 58px", md: "100px 62px minmax(300px, 1fr) 78px 76px" }, alignItems: "center", minHeight: 72, px: { xs: 1.5, md: 2.5 }, py: 1.25, borderBottom: "1px solid #edf1f5", bgcolor: isToday ? "#f5f8ff" : "transparent" }}>
            <Box><Typography sx={{ fontSize: 11, fontWeight: 800, color: "#334155" }}>{dayName}</Typography><Typography sx={{ fontSize: 10, color: "#718096" }}>{getDayLabel(day)}</Typography>{isToday && <Chip label="Today" size="small" sx={{ mt: 0.25, height: 17, fontSize: 9, fontWeight: 700, bgcolor: "#e8efff", color: "#315acb" }} />}</Box>
            <Typography sx={{ display: { xs: "none", md: "block" }, fontSize: 11, color: "#64748b", fontFamily: "monospace" }}>{checkIn === null ? "--:--" : formatClock(checkIn)}</Typography>
            <Box sx={{ gridColumn: { xs: "2", md: "3" }, position: "relative", height: 38, display: "flex", alignItems: "center" }}>
              <Box sx={{ position: "absolute", left: 0, right: 0, height: 3, bgcolor: isWeekend ? "#e2e8f0" : "#e8edf3", borderRadius: 2 }} />
              {!isWeekend && status !== "PENDING" && <Box sx={{ position: "absolute", left: `${startPosition}%`, width: `${Math.max(endPosition - startPosition, status === "ABSENT" ? 100 : 1)}%`, height: 4, bgcolor: color, background: isLive ? `repeating-linear-gradient(90deg, ${color} 0 10px, rgba(255,255,255,0.7) 10px 14px)` : color, backgroundSize: isLive ? "28px 100%" : "auto", borderRadius: 2, animation: isLive ? "weeklyTrainMotion 0.8s linear infinite, weeklyProgressPulse 1.8s ease-in-out infinite" : "none", "@keyframes weeklyTrainMotion": { from: { backgroundPosition: "0 0" }, to: { backgroundPosition: "28px 0" } }, "@keyframes weeklyProgressPulse": { "0%, 100%": { opacity: 0.55 }, "50%": { opacity: 1 } } }} />}
              {!isWeekend && status !== "PENDING" && <Box sx={{ position: "absolute", left: `${status === "ABSENT" ? 0 : startPosition}%`, width: 8, height: 8, transform: "translateX(-50%)", borderRadius: "50%", bgcolor: color, boxShadow: isLive ? `0 0 0 4px ${color}22` : "none" }} />}
              <Typography sx={{ position: "absolute", top: 22, left: status === "ABSENT" ? 0 : `${startPosition}%`, fontSize: 10, color, fontWeight: 700, whiteSpace: "nowrap" }}>{status === "ABSENT" ? "Absent" : status === "LEAVE" ? "Leave" : status === "WEEKEND" ? "Weekend" : status === "PENDING" ? "Not recorded" : isLive ? `In progress · Now ${formatClock(endMinutes)}` : status === "COMPLETED" || status === "PRESENT" ? "Present" : "Checked in"}</Typography>
              {isLive && <Box sx={{ position: "absolute", left: `${endPosition}%`, top: 1, transform: "translateX(-50%)", display: "flex", flexDirection: "column", alignItems: "center" }}><Box sx={{ width: 8, height: 8, borderRadius: "50%", bgcolor: color, boxShadow: `0 0 0 4px ${color}22` }} /><Typography sx={{ mt: 0.25, fontSize: 9, color, fontWeight: 800, whiteSpace: "nowrap" }}>NOW</Typography></Box>}
            </Box>
            <Typography sx={{ display: { xs: "none", md: "block" }, fontSize: 11, color: "#64748b", fontFamily: "monospace" }}>{checkOut === null ? (isLive ? "Now" : "--:--") : formatClock(checkOut)}</Typography>
            <Box sx={{ textAlign: "right" }}><Typography sx={{ fontSize: 11, fontFamily: "monospace", fontWeight: 700, color: "#334155" }}>{formatDuration(duration)}</Typography><Typography sx={{ fontSize: 9, color: "#94a3b8" }}>worked</Typography></Box>
          </Box>
        );
      })}

      <Box sx={{ display: "flex", gap: 2.5, flexWrap: "wrap", px: 2.5, py: 1.5, bgcolor: "#fbfcfe", color: "#64748b", fontSize: 10 }}>
        {[['#16a34a', "Present"], ['#f43f5e', "Absent"], ['#f59e0b', "Leave"], ['#2563eb', "In progress"], ['#cbd5e1', "Weekend"]].map(([color, label]) => <Box key={label} sx={{ display: "flex", alignItems: "center", gap: 0.75 }}><Box sx={{ width: 7, height: 7, borderRadius: "50%", bgcolor: color }} />{label}</Box>)}
      </Box>
    </Paper>
  );
}