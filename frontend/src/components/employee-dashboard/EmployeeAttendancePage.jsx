import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Box,
  Alert,
  Button,
  Chip,
  FormControl,
  IconButton,
  MenuItem,
  Paper,
  Select,
  Tab,
  Tabs,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import { ChevronLeft, ChevronRight, CalendarMonthOutlined, ViewListOutlined, ViewWeekOutlined } from "@mui/icons-material";
import { getHistory } from "../../lib/attendance.js";
import { formatDuration, formatTime } from "../../lib/date.js";
import { StatusBadge } from "../StatusBadge.jsx";
import { indexActiveHolidays, useActiveHolidays } from "../../data/holidayCalendar.js";

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const WEEKDAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"];
const STATUSES = ["All Status", "PRESENT", "INCOMPLETE", "LEAVE", "ABSENT"];

function dateKey(year, month, day) {
  return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function localDateKey(date = new Date()) {
  return dateKey(date.getFullYear(), date.getMonth(), date.getDate());
}

function isWeekend(year, month, day) {
  const weekday = new Date(year, month, day).getDay();
  return weekday === 0 || weekday === 6;
}

function displayStatus(status) {
  if (status === "PRESENT") return "Present";
  if (status === "INCOMPLETE") return "Checked In";
  if (status === "LEAVE") return "On Leave";
  if (status === "HOLIDAY") return "Holiday";
  if (status === "WEEKEND") return "Weekend";
  return status || "Pending";
}

function statusColor(status) {
  if (status === "PRESENT") return { background: "#ecfdf5", border: "#bbf7d0", color: "#047857" };
  if (status === "LEAVE") return { background: "#fffbeb", border: "#fde68a", color: "#b45309" };
  if (status === "INCOMPLETE") return { background: "#eff6ff", border: "#bfdbfe", color: "#1d4ed8" };
  if (status === "HOLIDAY") return { background: "#fffbeb", border: "#fde68a", color: "#b45309" };
  if (status === "WEEKEND") return { background: "#f8fafc", border: "#e2e8f0", color: "#64748b" };
  return { background: "#fff1f2", border: "#fecdd3", color: "#be123c" };
}

export function EmployeeAttendancePage() {
  const now = new Date();
  const [tab, setTab] = useState(0);
  const [view, setView] = useState("Month");
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth());
  const [statusFilter, setStatusFilter] = useState("All Status");
  const { data: records = [], isLoading, isError, refetch } = useQuery({ queryKey: ["attendanceHistory"], queryFn: getHistory });
  const { data: activeHolidays = [], isError: holidaysError } = useActiveHolidays();
  const holidayByDate = useMemo(() => indexActiveHolidays(activeHolidays), [activeHolidays]);

  const recordsByDate = useMemo(() => new Map(records.map((record) => [record.date, record])), [records]);
  const monthRecords = useMemo(() => records.filter((record) => {
    if (!record.date?.startsWith(`${year}-${String(month + 1).padStart(2, "0")}`)) return false;
    return statusFilter === "All Status" || record.status === statusFilter;
  }).sort((a, b) => b.date.localeCompare(a.date)), [month, records, statusFilter, year]);

  const stats = useMemo(() => {
    const monthPrefix = `${year}-${String(month + 1).padStart(2, "0")}`;
    const current = records.filter((record) => record.date?.startsWith(monthPrefix));
    return [
      ["Present", current.filter((record) => record.status === "PRESENT").length, "#16a34a"],
      ["Absent", current.filter((record) => record.status === "ABSENT").length, "#f43f5e"],
      ["On Leave", current.filter((record) => record.status === "LEAVE").length, "#f59e0b"],
      ["Missing Checkout", current.filter((record) => record.status === "INCOMPLETE" && record.check_in && !record.check_out).length, "#f97316"],
      ["On Duty", 0, "#2563eb"],
      ["Work From Home", 0, "#7c3aed"],
    ];
  }, [month, records, year]);

  const calendarCells = useMemo(() => {
    const firstWeekday = new Date(year, month, 1).getDay();
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    return Array.from({ length: Math.ceil((firstWeekday + daysInMonth) / 7) * 7 }, (_, index) => {
      const day = index - firstWeekday + 1;
      return day > 0 && day <= daysInMonth ? day : null;
    });
  }, [month, year]);

  const changeMonth = (offset) => {
    const next = new Date(year, month + offset, 1);
    setYear(next.getFullYear());
    setMonth(next.getMonth());
  };

  if (isLoading) return <Paper sx={{ p: 5, textAlign: "center" }}><Typography color="text.secondary">Loading attendance...</Typography></Paper>;
  if (isError) return <Paper sx={{ p: 5, textAlign: "center" }}><Typography color="error" sx={{ mb: 2 }}>Could not load attendance.</Typography><Button variant="contained" onClick={refetch}>Try again</Button></Paper>;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 2.5 }}>
      <Box>
        <Typography variant="h5" sx={{ fontWeight: 700, color: "#0f172a" }}>My Attendance</Typography>
        <Typography variant="body2" sx={{ color: "#64748b", mt: 0.5 }}>View your attendance history and daily working hours.</Typography>
      </Box>

      <Tabs value={tab} onChange={(_, value) => setTab(value)} sx={{ borderBottom: "1px solid #e2e8f0", minHeight: 42 }}>
        <Tab label="Attendance Summary" sx={{ minHeight: 42, textTransform: "none", fontSize: 12, fontWeight: 600 }} />
        <Tab label="Regularization" sx={{ minHeight: 42, textTransform: "none", fontSize: 12, fontWeight: 600 }} />
        <Tab label="On Duty" sx={{ minHeight: 42, textTransform: "none", fontSize: 12, fontWeight: 600 }} />
      </Tabs>

      {tab !== 0 ? (
        <Paper sx={{ p: 5, textAlign: "center", border: "1px solid #e2e8f0", boxShadow: "none" }}>
          <Typography sx={{ fontWeight: 700 }}>{tab === 1 ? "Regularization" : "On Duty"}</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>Use the dedicated request page to manage these records.</Typography>
        </Paper>
      ) : (
        <>
          {holidaysError && <Alert severity="warning">Holiday data could not be loaded. Holiday labels may be missing.</Alert>}
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "repeat(2, 1fr)", sm: "repeat(3, 1fr)", xl: "repeat(6, 1fr)" }, gap: 1.25 }}>
            {stats.map(([label, value, color]) => <Paper key={label} sx={{ p: 1.5, border: "1px solid #dbe3ee", borderRadius: 2, boxShadow: "0 1px 2px rgba(15,23,42,0.04)" }}><Typography sx={{ fontSize: 10, color: "#64748b" }}>{label}</Typography><Typography sx={{ mt: 0.5, fontSize: 15, fontWeight: 800, color }}>{value} days</Typography></Paper>)}
          </Box>

          <Paper sx={{ overflow: "hidden", border: "1px solid #dbe3ee", borderRadius: 2.5, boxShadow: "none" }}>
            <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 1.5, p: 1.5, borderBottom: "1px solid #e2e8f0" }}>
              <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
                <IconButton size="small" onClick={() => changeMonth(-1)} aria-label="Previous month"><ChevronLeft fontSize="small" /></IconButton>
                <Typography sx={{ minWidth: 130, textAlign: "center", fontSize: 12, fontWeight: 800 }}>{MONTHS[month]} {year}</Typography>
                <IconButton size="small" onClick={() => changeMonth(1)} aria-label="Next month"><ChevronRight fontSize="small" /></IconButton>
                <Button size="small" onClick={() => { setYear(now.getFullYear()); setMonth(now.getMonth()); }} sx={{ textTransform: "none", fontSize: 11 }}>Today</Button>
              </Box>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <FormControl size="small" sx={{ minWidth: 125 }}><Select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} sx={{ fontSize: 11, height: 32 }}>{STATUSES.map((status) => <MenuItem key={status} value={status} sx={{ fontSize: 11 }}>{status === "All Status" ? status : displayStatus(status)}</MenuItem>)}</Select></FormControl>
                <Box sx={{ display: "flex", border: "1px solid #dbe3ee", borderRadius: 1.5, p: 0.25 }}>
                  {[{ label: "Month", icon: <CalendarMonthOutlined fontSize="inherit" /> }, { label: "Week", icon: <ViewWeekOutlined fontSize="inherit" /> }, { label: "List", icon: <ViewListOutlined fontSize="inherit" /> }].map((item) => <Button key={item.label} size="small" onClick={() => setView(item.label)} startIcon={item.icon} sx={{ minWidth: 0, px: 1, fontSize: 10, textTransform: "none", bgcolor: view === item.label ? "#eef2ff" : "transparent", color: view === item.label ? "#4f46e5" : "#64748b" }}>{item.label}</Button>)}
                </Box>
              </Box>
            </Box>

            {view === "Month" && <Box sx={{ overflowX: "auto" }}>
              <Box sx={{ minWidth: 700, display: "grid", gridTemplateColumns: "repeat(7, 1fr)" }}>
                {WEEKDAYS.map((weekday) => <Box key={weekday} sx={{ p: 1, textAlign: "center", bgcolor: "#f8fafc", borderBottom: "1px solid #e2e8f0", color: "#64748b", fontSize: 10, fontWeight: 800 }}>{weekday}</Box>)}
                {calendarCells.map((day, index) => {
                  const key = day ? dateKey(year, month, day) : `empty-${index}`;
                  const record = day ? recordsByDate.get(key) : null;
                  const today = day && key === localDateKey();
                  const weekend = day && isWeekend(year, month, day);
                  const displayRecord = weekend && ["ABSENT", "NOT_CHECKED_IN", "YET_TO_CHECK_IN"].includes(record?.status) ? null : record;
                  const holiday = day && holidayByDate.get(key);
                  const holidayStatus = holiday && (!record || ["ABSENT", "NOT_CHECKED_IN", "YET_TO_CHECK_IN"].includes(record.status)) && !weekend;
                  const colors = displayRecord ? statusColor(displayRecord.status) : null;
                  return <Box key={key} sx={{ minHeight: 94, p: 0.75, borderRight: "1px solid #e2e8f0", borderBottom: "1px solid #e2e8f0", bgcolor: !day ? "#f8fafc" : weekend ? "#fbfcfe" : "#fff", opacity: record && statusFilter !== "All Status" && record.status !== statusFilter ? 0.3 : 1 }}>
                    {day && <><Typography sx={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: today ? 24 : "auto", height: today ? 24 : "auto", borderRadius: "50%", bgcolor: today ? "#4f39ee" : "transparent", color: today ? "#fff" : "#334155", fontSize: 11, fontWeight: 700 }}>{day}</Typography>{holidayStatus ? <Box sx={{ mt: 0.75, p: 0.75, borderRadius: 1, borderLeft: "3px solid #f59e0b", bgcolor: "#fffbeb", color: "#b45309" }}><Typography sx={{ fontSize: 10, fontWeight: 800 }}>Holiday</Typography><Typography title={holiday.name} sx={{ mt: 0.25, fontSize: 9, color: "#64748b" }}>{holiday.name}</Typography></Box> : displayRecord ? <Box sx={{ mt: 0.75, p: 0.75, borderRadius: 1, borderLeft: `3px solid ${colors.border}`, bgcolor: colors.background, color: colors.color }}><Typography sx={{ fontSize: 10, fontWeight: 800 }}>{displayStatus(displayRecord.status)}</Typography>{displayRecord.status === "HOLIDAY" && displayRecord.holiday_name ? <Typography sx={{ mt: 0.25, fontSize: 9 }}>{displayRecord.holiday_name}</Typography> : <Typography sx={{ mt: 0.25, fontSize: 10 }}>{formatDuration(displayRecord.working_duration)}</Typography>}</Box> : weekend ? <Box sx={{ mt: 1 }}><Typography sx={{ fontSize: 10, color: "#64748b", fontWeight: 700 }}>Weekend</Typography>{holiday && <Typography title={holiday.name} sx={{ fontSize: 9, color: "#6366f1" }}>{holiday.name}</Typography>}</Box> : null}</>}
                  </Box>;
                })}
              </Box>
            </Box>}
            {view === "Week" && <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(7, 1fr)" }, gap: 1, p: 1.5 }}>{Array.from({ length: 7 }, (_, index) => { const date = new Date(year, month, 1 + index); const key = localDateKey(date); const record = recordsByDate.get(key); const holiday = holidayByDate.get(key); const weekend = isWeekend(date.getFullYear(), date.getMonth(), date.getDate()); const staleNonAttendance = ["ABSENT", "NOT_CHECKED_IN", "YET_TO_CHECK_IN"].includes(record?.status); const showHoliday = holiday && (!record || staleNonAttendance) && !weekend; const showWeekend = weekend && (!record || staleNonAttendance); return <Box key={index} sx={{ p: 1.25, minHeight: 120, border: "1px solid #e2e8f0", borderRadius: 1.5 }}><Typography sx={{ fontSize: 10, fontWeight: 800 }}>{date.toLocaleDateString("en-US", { weekday: "short" })}</Typography><Typography sx={{ fontSize: 11, color: "#64748b" }}>{date.toLocaleDateString("en-US", { month: "short", day: "numeric" })}</Typography>{showHoliday || showWeekend ? <Box sx={{ mt: 2 }}><StatusBadge status={showWeekend ? "WEEKEND" : "HOLIDAY"} />{holiday && <Typography sx={{ mt: 0.5, fontSize: 10, color: "#64748b" }}>{holiday.name}</Typography>}</Box> : record ? <Box sx={{ mt: 2 }}><StatusBadge status={record.status} />{record.status === "HOLIDAY" && record.holiday_name ? <Typography sx={{ mt: 0.5, fontSize: 10, color: "#64748b" }}>{record.holiday_name}</Typography> : <><Typography sx={{ mt: 1, fontSize: 10, color: "#64748b" }}>In {record.check_in ? formatTime(record.check_in) : "--:--"}</Typography><Typography sx={{ fontSize: 10, color: "#64748b" }}>Out {record.check_out ? formatTime(record.check_out) : "--:--"}</Typography></>}</Box> : null}</Box>; })}</Box>}
            {view === "List" && <Table size="small"><TableHead sx={{ bgcolor: "#f8fafc" }}><TableRow>{["Date", "Status", "Check In", "Check Out", "Working Hours"].map((heading) => <TableCell key={heading} sx={{ fontSize: 10, fontWeight: 800, color: "#64748b", textTransform: "uppercase" }}>{heading}</TableCell>)}</TableRow></TableHead><TableBody>{monthRecords.map((record) => <TableRow key={record.date}><TableCell sx={{ fontSize: 12, fontWeight: 700 }}>{new Date(`${record.date}T00:00:00`).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}</TableCell><TableCell><StatusBadge status={record.status} /></TableCell><TableCell sx={{ fontSize: 11 }}>{record.check_in ? formatTime(record.check_in) : "--:--"}</TableCell><TableCell sx={{ fontSize: 11 }}>{record.check_out ? formatTime(record.check_out) : "--:--"}</TableCell><TableCell sx={{ fontSize: 11 }}>{formatDuration(record.working_duration)}</TableCell></TableRow>)}</TableBody></Table>}
          </Paper>
        </>
      )}
    </Box>
  );
}
