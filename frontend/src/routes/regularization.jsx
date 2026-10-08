import React, { useCallback, useEffect, useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import {
  Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions,
  DialogContent, DialogTitle, MenuItem, Paper, Table, TableBody,
  TableCell, TableContainer, TableHead, TableRow, TextField, Typography,
} from "@mui/material";
import { RequireAuth } from "../components/RequireAuth.jsx";
import { createRegularizationRequest, fetchMyRegularizationQuota, fetchMyRegularizationRequests, uploadFile } from "../lib/api.js";
import { getHistory } from "../lib/attendance.js";
import { useFeedback } from "../feedback/FeedbackProvider.jsx";
import { getErrorMessage } from "../feedback/errorMessage.js";
import { useActiveHolidays } from "../data/holidayCalendar.js";

const REQUEST_TYPES = [
  { value: "FORGOT_CHECK_IN", label: "Forgot Check-In" },
  { value: "FORGOT_CHECK_OUT", label: "Forgot Check-Out" },
  { value: "INCORRECT_ATTENDANCE", label: "Incorrect Attendance" },
  { value: "SYSTEM_ISSUE", label: "System Issue" },
];
const STATUS_COLORS = { PENDING: "warning", APPROVED: "success", REJECTED: "error" };
const TODAY = () => localDateString();

function localDateString(date = new Date()) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}
function requestCountLabel(count) {
  return `${count} ${count === 1 ? "request" : "requests"}`;
}
function shiftDate(value, offset) {
  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(year, month - 1, day + offset, 12);
  return localDateString(date);
}
function weekdaysBetween(start, end) {
  const dates = [];
  for (let value = start; value <= end; value = shiftDate(value, 1)) {
    const [year, month, day] = value.split("-").map(Number);
    const weekday = new Date(year, month - 1, day, 12).getDay();
    if (weekday !== 0 && weekday !== 6) dates.push(value);
  }
  return dates;
}
function isWorkingDay(value) {
  const [year, month, day] = value.split("-").map(Number);
  const weekday = new Date(year, month - 1, day, 12).getDay();
  return weekday !== 0 && weekday !== 6;
}
function formatTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
function dateLabel(value) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day, 12).toLocaleDateString();
}
function weekStart(value) {
  const [year, month, day] = value.split("-").map(Number);
  const date = new Date(year, month - 1, day, 12);
  return shiftDate(value, -((date.getDay() + 6) % 7));
}
function weekLabel(monday) {
  const sunday = shiftDate(monday, 6);
  const [startYear, startMonth, startDay] = monday.split("-").map(Number);
  const [endYear, endMonth, endDay] = sunday.split("-").map(Number);
  const start = new Date(startYear, startMonth - 1, startDay, 12);
  const end = new Date(endYear, endMonth - 1, endDay, 12);
  const sameMonth = start.getMonth() === end.getMonth();
  return sameMonth
    ? `${start.toLocaleString([], { month: "short" })} ${start.getDate()} – ${end.toLocaleString([], { month: "short" })} ${end.getDate()}, ${end.getFullYear()}`
    : `${start.toLocaleString([], { month: "short" })} ${start.getDate()} – ${end.toLocaleString([], { month: "short" })} ${end.getDate()}, ${end.getFullYear()}`;
}
function monthLabel(value) {
  const [year, month] = value.split("-").map(Number);
  return new Date(year, month - 1, 1, 12).toLocaleString([], { month: "long", year: "numeric" });
}
function getAvailableWeeks() {
  const today = TODAY();
  const currentMonday = weekStart(today);
  return [-2, -1, 0, 1, 2].map((offset) => shiftDate(currentMonday, offset * 7));
}
function getAvailableMonths() {
  const [year, month] = TODAY().split("-").map(Number);
  return [-2, -1, 0, 1, 2].map((offset) => {
    const date = new Date(year, month - 1 + offset, 1, 12);
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
  });
}

export const Route = createFileRoute("/regularization")({
  component: () => <RequireAuth><RegularizationPage /></RequireAuth>,
});

function RegularizationPage() {
  const { success, notifyError } = useFeedback();
  const { data: activeHolidays = [], isError: holidaysError } = useActiveHolidays();
  const holidayByDate = useMemo(() => new Map(activeHolidays.map((holiday) => [holiday.date, holiday])), [activeHolidays]);
  const [requests, setRequests] = useState([]);
  const [quota, setQuota] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [pageError, setPageError] = useState("");
  const [formError, setFormError] = useState("");
  const [periodType, setPeriodType] = useState("DAY");
  const [periodValue, setPeriodValue] = useState(TODAY());
  const [attachment, setAttachment] = useState(null);
  const [days, setDays] = useState({});
  const cutoff = new Date(TODAY()); cutoff.setDate(cutoff.getDate() - 2);
  const cutoffString = localDateString(cutoff);
  const currentWeekStart = weekStart(TODAY());

  const loadData = useCallback(async () => {
    setLoading(true);
    setPageError("");
    try {
      const [requestData, attendanceData, quotaData] = await Promise.all([
        fetchMyRegularizationRequests(),
        getHistory(),
        fetchMyRegularizationQuota(),
      ]);
      setRequests(Array.isArray(requestData) ? requestData : []);
      setHistory(Array.isArray(attendanceData) ? attendanceData : []);
      setQuota(quotaData);
    } catch (error) {
      setPageError(error.message || "Failed to load regularization information.");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { loadData(); }, [loadData]);

  const summary = useMemo(() => ({
    PENDING: requests.filter((item) => item.status === "PENDING").length,
    APPROVED: requests.filter((item) => item.status === "APPROVED").length,
    REJECTED: requests.filter((item) => item.status === "REJECTED").length,
  }), [requests]);

  const generatedDates = useMemo(() => {
    const today = TODAY();
    if (periodType === "DAY") return [periodValue].filter((date) => date <= today);
    if (periodType === "WEEK") {
      return weekdaysBetween(periodValue, shiftDate(periodValue, 6)).filter((date) => date <= today);
    }
    const [year, month] = periodValue.split("-").map(Number);
    const first = `${year}-${String(month).padStart(2, "0")}-01`;
    const lastDay = new Date(year, month, 0).getDate();
    return weekdaysBetween(first, `${year}-${String(month).padStart(2, "0")}-${lastDay}`).filter((date) => date <= today);
  }, [periodType, periodValue]);

  // Keep all selected-period rows visible; this separate list controls submission eligibility.
  const generatedPeriodDates = useMemo(
    () => generatedDates.filter(isWorkingDay),
    [generatedDates],
  );
  const submissionDates = generatedPeriodDates.filter((date) => date >= cutoffString && !holidayByDate.has(date));
  const normalizeDate = (value) => String(value ?? "").slice(0, 10);
  const attendanceByDate = useMemo(() => Object.fromEntries(
    history.map((row) => [normalizeDate(row.date), row]),
  ), [history]);
  const pendingDates = useMemo(() => new Set(requests.filter((item) => item.status === "PENDING").flatMap((item) => item.days?.map((day) => day.attendance_date) || [item.attendance_date])), [requests]);

  const openForm = () => {
    setFormError(""); setAttachment(null); setDays({}); setPeriodType("DAY"); setPeriodValue(TODAY()); setDialogOpen(true);
  };
  const setDayField = (date, field, value) => setDays((current) => ({
    ...current,
    [date]: { request_type: "INCORRECT_ATTENDANCE", reason: "", description: "", requested_check_in: "", requested_check_out: "", ...current[date], [field]: value },
  }));

  const handleSubmit = async (event) => {
    event.preventDefault(); setFormError("");
    if (holidaysError) { setFormError("Holiday dates could not be verified. Reload the page before submitting."); return; }
    const selectedDays = submissionDates.filter((date) => {
      const day = days[date];
      return day && (day.requested_check_in || day.requested_check_out || day.reason.trim() || day.description.trim());
    });
    if (!selectedDays.length) { setFormError("Choose at least one attendance date and enter a correction."); return; }
    for (const date of selectedDays) {
      const day = days[date];
      if (!day.reason.trim()) { setFormError(`${dateLabel(date)}: add a reason.`); return; }
      if (!day.requested_check_in && !day.requested_check_out) { setFormError(`${dateLabel(date)}: enter a corrected check-in or check-out.`); return; }
      if (day.requested_check_in && day.requested_check_out && day.requested_check_out <= day.requested_check_in) { setFormError(`${dateLabel(date)}: check-out must be later than check-in.`); return; }
    }
    setSubmitting(true);
    try {
      let attachmentUrl = "";
      if (attachment) {
        try {
          const upload = await uploadFile(attachment);
          attachmentUrl = upload.file_url;
        } catch (uploadError) {
          notifyError(uploadError, { title: "Attachment upload failed", fallback: "Failed to upload the attachment." });
          return;
        }
      }
      const payloadDays = selectedDays.map((date) => {
        const day = days[date];
        return {
          attendance_date: date,
          request_type: day.request_type,
          requested_check_in: day.requested_check_in ? `${date}T${day.requested_check_in}:00` : null,
          requested_check_out: day.requested_check_out ? `${date}T${day.requested_check_out}:00` : null,
          reason: day.reason.trim(),
          description: day.description.trim(),
        };
      });
      await createRegularizationRequest({ period_type: periodType, days: payloadDays, attachment: attachmentUrl });
      success("Regularization request submitted.");
      setQuota((current) => current ? {
        ...current,
        weekly_used: Math.min(current.weekly_limit, current.weekly_used + 1),
        weekly_remaining: Math.max(0, current.weekly_limit - current.weekly_used - 1),
        monthly_used: Math.min(current.monthly_limit, current.monthly_used + 1),
        monthly_remaining: Math.max(0, current.monthly_limit - current.monthly_used - 1),
      } : current);
      setDialogOpen(false);
      await loadData();
    } catch (error) { setFormError(getErrorMessage(error, "Failed to submit the request.")); }
    finally { setSubmitting(false); }
  };

  const fileLimit = 5 * 1024 * 1024;
  const fileAccepted = ".pdf,.jpg,.jpeg,.png,.doc,.docx";
  const weeklyQuotaExhausted = Boolean(quota && quota.weekly_used >= quota.weekly_limit);
  const monthlyQuotaExhausted = Boolean(quota && quota.monthly_used >= quota.monthly_limit);
  const quotaExhausted = weeklyQuotaExhausted || monthlyQuotaExhausted;
  return <Box sx={{ maxWidth: 1280, mx: "auto", p: { xs: 2, md: 4 } }}>
    <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: { xs: "stretch", sm: "center" }, gap: 2, flexDirection: { xs: "column", sm: "row" }, mb: 3 }}>
      <Box><Typography variant="h4" fontWeight={750}>Regularization</Typography><Typography color="text.secondary" sx={{ mt: 0.5 }}>Request corrections for one day, a week, or a month.</Typography></Box>
      <Button variant="contained" onClick={openForm}>Request correction</Button>
    </Box>
    {pageError && <Alert severity="error" sx={{ mb: 2 }}>{pageError}</Alert>}
    <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(3, 1fr)" }, gap: 2, mb: 3 }}>
      {Object.entries(summary).map(([status, count]) => <Paper key={status} variant="outlined" sx={{ p: 2 }}><Typography variant="body2" color="text.secondary">{status}</Typography><Typography variant="h5" fontWeight={700}>{count}</Typography></Paper>)}
    </Box>
    <Paper variant="outlined" sx={{ p: 2, mb: 3, display: "flex", justifyContent: "space-between", alignItems: "center", gap: 2, flexWrap: "wrap" }}>
      <Box sx={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        <Box><Typography variant="subtitle2" color="text.secondary">This week · {quota ? `${dateLabel(quota.week_start)} – ${dateLabel(quota.week_end)}` : "Loading…"}</Typography>
          <Typography fontWeight={700}>{quota ? `${quota.weekly_used} of ${quota.weekly_limit} requests used` : "Weekly usage unavailable"}</Typography></Box>
        <Box><Typography variant="subtitle2" color="text.secondary">This month · {quota ? monthLabel(quota.month) : "Loading…"}</Typography>
          <Typography fontWeight={700}>{quota ? `${quota.monthly_used} of ${quota.monthly_limit} requests used` : "Monthly usage unavailable"}</Typography></Box>
      </Box>
      <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
        <Chip label={quota ? `${quota.weekly_remaining} left this week` : "— left this week"} color={quota?.weekly_remaining === 0 ? "warning" : "default"} variant="outlined" />
        <Chip label={quota ? `${quota.monthly_remaining} left this month` : "— left this month"} color={quota?.monthly_remaining === 0 ? "warning" : "default"} variant="outlined" />
      </Box>
    </Paper>
    <Paper variant="outlined">
      <Box sx={{ p: 2 }}><Typography variant="h6" fontWeight={700}>My requests</Typography></Box>
      {loading ? <Box sx={{ display: "flex", justifyContent: "center", p: 5 }}><CircularProgress size={28} /></Box> : requests.length === 0 ? <Typography color="text.secondary" sx={{ p: 3 }}>You have not submitted any regularization requests.</Typography> :
        <TableContainer><Table size="small"><TableHead><TableRow><TableCell>Period</TableCell><TableCell>Type</TableCell><TableCell>Requested times</TableCell><TableCell>Reason</TableCell><TableCell>Status</TableCell><TableCell>Review note</TableCell></TableRow></TableHead><TableBody>
          {requests.map((item) => <TableRow key={item.id} hover>
            <TableCell>{item.period_type && item.period_type !== "DAY" ? `${dateLabel(String(item.period_start).slice(0, 10))} – ${dateLabel(String(item.period_end).slice(0, 10))}` : dateLabel(item.attendance_date)}</TableCell>
            <TableCell>{item.period_type || "DAY"}{item.day_count > 1 ? ` (${item.day_count} days)` : ""}</TableCell>
            <TableCell>{formatTime(item.requested_check_in)} / {formatTime(item.requested_check_out)}</TableCell>
            <TableCell sx={{ maxWidth: 250 }}>{item.reason}</TableCell>
            <TableCell><Chip label={item.status} color={STATUS_COLORS[item.status] || "default"} size="small" /></TableCell>
            <TableCell>{item.rejection_reason || item.reviewed_by_name || "—"}</TableCell>
          </TableRow>)}
        </TableBody></Table></TableContainer>}
    </Paper>

    <Dialog open={dialogOpen} onClose={() => !submitting && setDialogOpen(false)} fullWidth maxWidth="lg">
      <Box component="form" onSubmit={handleSubmit}>
        <DialogTitle>Request attendance correction</DialogTitle>
        <DialogContent sx={{ display: "grid", gap: 2, pt: "8px !important" }}>
          {formError && <Alert severity="error">{formError}</Alert>}
          {holidaysError && <Alert severity="warning">Company holiday dates could not be loaded. Holiday eligibility is unavailable; reload before submitting.</Alert>}
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 2 }}>
            <TextField select label="Period" value={periodType} onChange={(event) => { setPeriodType(event.target.value); setDays({}); }}>
              <MenuItem value="DAY">Single day</MenuItem><MenuItem value="WEEK">Week</MenuItem><MenuItem value="MONTH">Month</MenuItem>
            </TextField>
            {periodType === "DAY" ? <TextField label="Date" type="date" value={periodValue} onChange={(event) => { setPeriodValue(event.target.value); setDays({}); }} inputProps={{ max: TODAY() }} InputLabelProps={{ shrink: true }} /> :
              periodType === "WEEK" ? <TextField select label="Week" value={periodValue} onChange={(event) => { setPeriodValue(event.target.value); setDays({}); }}>
                {getAvailableWeeks().map((monday) => <MenuItem key={monday} value={monday}>{weekLabel(monday)}</MenuItem>)}
              </TextField> : <TextField select label="Month" value={periodValue.slice(0, 7)} onChange={(event) => { setPeriodValue(`${event.target.value}-01`); setDays({}); }}>
                {getAvailableMonths().map((month) => <MenuItem key={month} value={month}>{monthLabel(month)}</MenuItem>)}
              </TextField>}
          </Box>
          <Alert severity={quotaExhausted ? "warning" : "info"}>
            You can submit up to {requestCountLabel(quota?.weekly_limit ?? 1)} per calendar week and {requestCountLabel(quota?.monthly_limit ?? 4)} per calendar month. Each request may include multiple attendance dates. Attendance corrections remain subject to the existing 48-hour window. Weekends and registered company holidays are not eligible attendance dates.
          </Alert>
          {weeklyQuotaExhausted && <Alert severity="error">You have reached this week’s allowance of {requestCountLabel(quota.weekly_limit)}.</Alert>}
          {monthlyQuotaExhausted && <Alert severity="error">You have reached this month’s allowance of {requestCountLabel(quota.monthly_limit)}.</Alert>}
          {generatedPeriodDates.length === 0 ? (
            <Paper variant="outlined" sx={{ p: 3, textAlign: "center" }}>
              <Typography color="text.secondary">No past weekdays are available in this period.</Typography>
            </Paper>
          ) : generatedPeriodDates.map((date) => {
            const day = days[date] || {};
            const attendance = attendanceByDate[date];
            const holiday = holidayByDate.get(date);
            const isMultiDay = periodType === "WEEK" || periodType === "MONTH";
            const dateEligible = isMultiDay ? date >= currentWeekStart : date >= cutoffString;
            const eligible = dateEligible && !pendingDates.has(date) && !holiday && !holidaysError;
            return <Paper key={date} data-attendance-date={date} variant="outlined" sx={{ p: 2, minWidth: 0 }}>
              <Box sx={{ display: "flex", justifyContent: "space-between", gap: 1, alignItems: "center", mb: 1 }}>
                <Typography fontWeight={700}>{dateLabel(date)}</Typography>
                {holiday && <Chip size="small" color="warning" label={`Holiday${holiday.name ? `: ${holiday.name}` : ""}`} />}
                {!eligible && !holiday && <Chip size="small" color="warning" label={pendingDates.has(date) ? "Pending request" : holidaysError ? "Holiday data unavailable" : "Outside allowed window"} />}
                <Chip size="small" variant="outlined" label={attendance ? attendance.status : "No attendance row"} />
              </Box>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>Current: {formatTime(attendance?.check_in)} – {formatTime(attendance?.check_out)}</Typography>
              <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr 1fr 1fr" }, gap: 1.5 }}>
                <TextField select label="Request type" value={day.request_type || "INCORRECT_ATTENDANCE"} disabled={!eligible} onChange={(event) => setDayField(date, "request_type", event.target.value)}>
                  {REQUEST_TYPES.map((type) => <MenuItem key={type.value} value={type.value}>{type.label}</MenuItem>)}
                </TextField>
                <TextField label="Corrected check-in" type="time" value={day.requested_check_in || ""} disabled={!eligible} onChange={(event) => setDayField(date, "requested_check_in", event.target.value)} InputLabelProps={{ shrink: true }} />
                <TextField label="Corrected check-out" type="time" value={day.requested_check_out || ""} disabled={!eligible} onChange={(event) => setDayField(date, "requested_check_out", event.target.value)} InputLabelProps={{ shrink: true }} />
                <TextField label="Reason" value={day.reason || ""} disabled={!eligible} onChange={(event) => setDayField(date, "reason", event.target.value)} />
              </Box>
              {eligible && <TextField fullWidth label="Additional details (optional)" value={day.description || ""} onChange={(event) => setDayField(date, "description", event.target.value)} sx={{ mt: 1.5 }} />}
            </Paper>;
          })}
          <Box><Button component="label" variant="outlined">{attachment ? attachment.name : "Attach supporting document"}<input hidden type="file" accept={fileAccepted} onChange={(event) => { const file = event.target.files?.[0] || null; if (file && file.size > fileLimit) { setFormError("Attachment must be 5 MB or smaller."); setAttachment(null); } else { setFormError(""); setAttachment(file); } }} /></Button><Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>PDF, image, or Word document; max 5 MB</Typography></Box>
        </DialogContent>
        <DialogActions sx={{ p: 2, justifyContent: "space-between" }}>
          <Typography variant="body2" color={quotaExhausted ? "error.main" : "text.secondary"}>
            {quota ? `${quota.weekly_used} / ${quota.weekly_limit} this week · ${quota.monthly_used} / ${quota.monthly_limit} this month` : "Quota usage unavailable"}
          </Typography>
          <Box sx={{ display: "flex", gap: 1 }}>
            <Button onClick={() => setDialogOpen(false)} disabled={submitting}>Cancel</Button>
            <Button type="submit" variant="contained" disabled={submitting || quotaExhausted || holidaysError}>{submitting ? "Submitting…" : "Submit request"}</Button>
          </Box>
        </DialogActions>
      </Box>
    </Dialog>
  </Box>;
}
