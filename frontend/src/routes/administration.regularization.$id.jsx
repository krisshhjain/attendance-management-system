import React, { useEffect, useState } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Divider,
  Paper,
  TextField,
  Typography,
} from "@mui/material";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import { RequireAuth } from "../components/RequireAuth.jsx";
import {
  approveRegularizationRequest,
  fetchAdminRegularizationRequest,
  rejectRegularizationRequest,
} from "../lib/api.js";

export const Route = createFileRoute("/administration/regularization/$id")({
  component: () => (
    <RequireAuth>
      <RegularizationReviewPage />
    </RequireAuth>
  ),
});

function toTimeInput(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

function displayTime(value) {
  if (!value) return "Not recorded";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Not recorded"
    : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function Detail({ label, children }) {
  return (
    <Box>
      <Typography variant="caption" color="text.secondary">{label}</Typography>
      <Typography variant="body1" fontWeight={600}>{children || "—"}</Typography>
    </Box>
  );
}

function RegularizationReviewPage() {
  const { id } = Route.useParams();
  const navigate = useNavigate();
  const [request, setRequest] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [checkIn, setCheckIn] = useState("");
  const [checkOut, setCheckOut] = useState("");
  const [dayTimes, setDayTimes] = useState({});
  const [rejectionReason, setRejectionReason] = useState("");

  const loadRequest = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchAdminRegularizationRequest(id);
      setRequest(data);
      setCheckIn(toTimeInput(data.approved_check_in || data.requested_check_in || data.existing_check_in));
      setCheckOut(toTimeInput(data.approved_check_out || data.requested_check_out || data.existing_check_out));
      setDayTimes(Object.fromEntries((data.days || []).map((day) => [day.id || day.attendance_date, {
        check_in: toTimeInput(day.approved_check_in || day.requested_check_in || day.existing_check_in),
        check_out: toTimeInput(day.approved_check_out || day.requested_check_out || day.existing_check_out),
      }])));
    } catch (loadError) {
      setError(loadError.message || "Could not load this regularization request.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRequest();
  }, [id]);

  const handleApprove = async () => {
    if (!request) return;
    setError("");
    const requestDays = request.days || [];
    if (requestDays.length > 1 && requestDays.some((day) => {
      const times = dayTimes[day.id || day.attendance_date] || {};
      return !times.check_in && !times.check_out;
    })) {
      setError("Enter at least one final time for every requested date.");
      return;
    }
    if (requestDays.length > 1 && requestDays.some((day) => {
      const times = dayTimes[day.id || day.attendance_date] || {};
      return times.check_in && times.check_out && times.check_out <= times.check_in;
    })) {
      setError("Each check-out must be later than its check-in.");
      return;
    }
    if (requestDays.length <= 1 && !checkIn && !checkOut) {
      setError("Enter at least one final check-in or check-out time.");
      return;
    }
    if (requestDays.length <= 1 && checkIn && checkOut && checkOut <= checkIn) {
      setError("Final check-out must be later than final check-in.");
      return;
    }
    const dateTime = (date, time) => time ? `${date}T${time}:00` : null;
    setSubmitting(true);
    try {
      if (requestDays.length > 1 || requestDays.some((day) => day.id)) {
        await approveRegularizationRequest(id, { days: requestDays.filter((day) => day.id).map((day) => {
          const key = day.id || day.attendance_date;
          const times = dayTimes[key] || {};
          return { id: day.id, check_in: dateTime(day.attendance_date, times.check_in), check_out: dateTime(day.attendance_date, times.check_out) };
        }) });
      } else {
        await approveRegularizationRequest(id, {
          check_in: dateTime(request.attendance_date, checkIn),
          check_out: dateTime(request.attendance_date, checkOut),
        });
      }
      await loadRequest();
    } catch (actionError) {
      setError(actionError.message || "Approval failed.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleReject = async () => {
    if (!rejectionReason.trim()) {
      setError("A rejection reason is required.");
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      await rejectRegularizationRequest(id, rejectionReason.trim());
      await loadRequest();
    } catch (actionError) {
      setError(actionError.message || "Rejection failed.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <Box sx={{ minHeight: "60vh", display: "grid", placeItems: "center" }}><CircularProgress /></Box>;
  }

  if (!request) {
    return (
      <Box sx={{ maxWidth: 900, mx: "auto", p: 3 }}>
        <Button startIcon={<ArrowBackIcon />} onClick={() => navigate({ to: "/administration" })} sx={{ mb: 2 }}>Back to Administration</Button>
        <Alert severity="error">{error || "Regularization request not found."}</Alert>
      </Box>
    );
  }

  const isPending = request.status === "PENDING";
  return (
    <Box sx={{ maxWidth: 1000, mx: "auto", p: { xs: 2, md: 4 } }}>
      <Button startIcon={<ArrowBackIcon />} onClick={() => navigate({ to: "/administration" })} sx={{ mb: 2 }}>Back to Administration</Button>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 2, mb: 3 }}>
        <Box>
          <Typography variant="h4" fontWeight={750}>{isPending ? "Review Regularization Request" : "Regularization Request"}</Typography>
          <Typography color="text.secondary">Request #{request.id}</Typography>
        </Box>
        <Chip label={request.status} color={request.status === "APPROVED" ? "success" : request.status === "REJECTED" ? "error" : "warning"} />
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Card variant="outlined" sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="h6" fontWeight={700} sx={{ mb: 2 }}>Employee and request</Typography>
          <Box sx={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 2 }}>
            <Detail label="Employee">{request.employee_name}</Detail>
            <Detail label="Employee ID">{request.employee_id}</Detail>
            <Detail label="Email">{request.employee_email}</Detail>
            <Detail label={request.period_type === "DAY" ? "Attendance date" : "Period"}>{request.period_type !== "DAY" && request.period_start ? `${new Date(`${request.period_start}T00:00:00`).toLocaleDateString()} – ${new Date(`${request.period_end}T00:00:00`).toLocaleDateString()}` : request.attendance_date ? new Date(`${request.attendance_date}T00:00:00`).toLocaleDateString() : "—"}</Detail>
            <Detail label="Request type">{request.request_type?.replaceAll("_", " ")}</Detail>
            <Detail label="Status">{request.status}</Detail>
          </Box>
        </CardContent>
      </Card>

      {(request.days || []).length > 1 ? (request.days || []).map((day) => {
        const key = day.id || day.attendance_date;
        const times = dayTimes[key] || {};
        return <Card key={key} variant="outlined" sx={{ mb: 2 }}><CardContent>
          <Typography variant="h6" fontWeight={700} sx={{ mb: 2 }}>{new Date(`${day.attendance_date}T00:00:00`).toLocaleDateString()} · {day.request_type?.replaceAll("_", " ")}</Typography>
          <Typography variant="body2" sx={{ mb: 1 }}>Reason: {day.reason}</Typography>
          {day.description && <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>{day.description}</Typography>}
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(3, 1fr)" }, gap: 2 }}>
            <Typography variant="subtitle2" />
            <Typography variant="subtitle2" fontWeight={700}>Check-in</Typography>
            <Typography variant="subtitle2" fontWeight={700}>Check-out</Typography>
            <Typography fontWeight={600}>Current</Typography>
            <Typography>{displayTime(day.existing_check_in)}</Typography>
            <Typography>{displayTime(day.existing_check_out)}</Typography>
            <Typography fontWeight={600}>Employee requested</Typography>
            <Typography>{displayTime(day.requested_check_in)}</Typography>
            <Typography>{displayTime(day.requested_check_out)}</Typography>
            {request.status === "APPROVED" && <>
              <Typography fontWeight={600}>Final approved</Typography>
              <Typography>{displayTime(day.approved_check_in)}</Typography>
              <Typography>{displayTime(day.approved_check_out)}</Typography>
            </>}
            {isPending && <>
              <Typography fontWeight={600}>Final timing</Typography>
              <TextField type="time" size="small" label="Final check-in" value={times.check_in || ""} onChange={(event) => setDayTimes((current) => ({ ...current, [key]: { ...times, check_in: event.target.value } }))} InputLabelProps={{ shrink: true }} />
              <TextField type="time" size="small" label="Final check-out" value={times.check_out || ""} onChange={(event) => setDayTimes((current) => ({ ...current, [key]: { ...times, check_out: event.target.value } }))} InputLabelProps={{ shrink: true }} />
            </>}
          </Box>
        </CardContent></Card>;
      }) : <Card variant="outlined" sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="h6" fontWeight={700} sx={{ mb: 2 }}>Attendance times</Typography>
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(3, 1fr)" }, gap: 2 }}>
            <Typography variant="subtitle2" /><Typography variant="subtitle2" fontWeight={700}>Check-in</Typography><Typography variant="subtitle2" fontWeight={700}>Check-out</Typography>
            <Typography fontWeight={600}>Current</Typography><Typography>{displayTime(request.existing_check_in)}</Typography><Typography>{displayTime(request.existing_check_out)}</Typography>
            <Typography fontWeight={600}>Employee requested</Typography><Typography>{displayTime(request.requested_check_in)}</Typography><Typography>{displayTime(request.requested_check_out)}</Typography>
            {isPending && <><Typography fontWeight={600}>Final timing</Typography><TextField type="time" size="small" label="Final check-in" value={checkIn} onChange={(event) => setCheckIn(event.target.value)} InputLabelProps={{ shrink: true }} /><TextField type="time" size="small" label="Final check-out" value={checkOut} onChange={(event) => setCheckOut(event.target.value)} InputLabelProps={{ shrink: true }} /></>}
          </Box>
        </CardContent>
      </Card>}

      <Card variant="outlined" sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="h6" fontWeight={700}>Employee reason</Typography>
          <Typography sx={{ mt: 1, whiteSpace: "pre-wrap" }}>{request.reason}</Typography>
          {request.attachment && <Typography sx={{ mt: 1 }}><a href={request.attachment} target="_blank" rel="noreferrer">Open supporting attachment</a></Typography>}
          {request.description && <>
            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle2" fontWeight={700}>Additional details</Typography>
            <Typography sx={{ mt: 0.5, whiteSpace: "pre-wrap" }}>{request.description}</Typography>
          </>}
          {request.rejection_reason && <>
            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle2" fontWeight={700}>Rejection reason</Typography>
            <Typography sx={{ mt: 0.5, whiteSpace: "pre-wrap" }}>{request.rejection_reason}</Typography>
          </>}
          {request.reviewed_by_name && <Typography variant="caption" display="block" color="text.secondary" sx={{ mt: 2 }}>
            Reviewed by {request.reviewed_by_name}{request.reviewed_at ? ` · ${new Date(request.reviewed_at).toLocaleString()}` : ""}
          </Typography>}
        </CardContent>
      </Card>

      {isPending && <Paper variant="outlined" sx={{ p: 2.5 }}>
        {!request.can_be_processed && <Alert severity="warning" sx={{ mb: 2 }}>This request is outside the processing window.</Alert>}
        <TextField fullWidth multiline minRows={2} label="Rejection reason (required to reject)" value={rejectionReason} onChange={(event) => setRejectionReason(event.target.value)} sx={{ mb: 2 }} />
        <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 1.5 }}>
          <Button color="error" variant="outlined" disabled={submitting || !rejectionReason.trim()} onClick={handleReject}>Reject</Button>
          <Button color="success" variant="contained" disabled={submitting || !request.can_be_processed} onClick={handleApprove}>{submitting ? "Saving…" : "Approve"}</Button>
        </Box>
      </Paper>}
    </Box>
  );
}
