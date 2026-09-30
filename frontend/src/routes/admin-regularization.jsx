import { useCallback, useEffect, useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  MenuItem,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import { RequireAuth } from "../components/RequireAuth.jsx";
import { useAuth } from "../lib/auth.jsx";
import {
  fetchAdminRegularizationQuotaPolicy,
  fetchAdminRegularizationRequests,
  updateAdminRegularizationQuotaPolicy,
} from "../lib/api.js";
import { useFeedback } from "../feedback/FeedbackProvider.jsx";

export const Route = createFileRoute("/admin-regularization")({
  component: () => (
    <RequireAuth>
      <AdminRegularizationPage />
    </RequireAuth>
  ),
});

function statusColor(status) {
  if (status === "APPROVED") return "success";
  if (status === "REJECTED") return "error";
  if (status === "PENDING") return "warning";
  return "default";
}

function requestPeriod(request) {
  if (request.period_type && request.period_type !== "DAY" && request.period_start) {
    const start = new Date(`${request.period_start}T00:00:00`).toLocaleDateString();
    const end = new Date(`${request.period_end}T00:00:00`).toLocaleDateString();
    return `${start} – ${end}`;
  }
  return request.attendance_date
    ? new Date(`${request.attendance_date}T00:00:00`).toLocaleDateString()
    : "—";
}

function formatTime(value) {
  return value
    ? new Date(value).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : "—";
}

function AdminRegularizationPage() {
  const { user, loginType } = useAuth();
  const canReview = Boolean(
    user?.is_staff || user?.is_superuser || user?.is_system_admin ||
    loginType === "admin" || loginType === "systemadmin",
  );
  const canConfigureQuota = Boolean(user?.is_superuser && loginType === "admin");
  const [requests, setRequests] = useState([]);
  const [statusFilter, setStatusFilter] = useState("PENDING");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [quotaPolicy, setQuotaPolicy] = useState(null);
  const [quotaDraft, setQuotaDraft] = useState({ weekly_limit: "1", monthly_limit: "4" });
  const [quotaLoading, setQuotaLoading] = useState(true);
  const [quotaSaving, setQuotaSaving] = useState(false);
  const [quotaError, setQuotaError] = useState("");
  const { success, notifyError } = useFeedback();

  const loadRequests = useCallback(async () => {
    if (!canReview) return;
    setLoading(true);
    setError("");
    try {
      const params = statusFilter === "ALL" ? {} : { status: statusFilter };
      const data = await fetchAdminRegularizationRequests(params);
      setRequests(Array.isArray(data) ? data : []);
    } catch (loadError) {
      setError(loadError.message || "Failed to load regularization requests.");
    } finally {
      setLoading(false);
    }
  }, [canReview, statusFilter]);

  useEffect(() => {
    loadRequests();
  }, [loadRequests]);

  const loadQuotaPolicy = useCallback(async () => {
    if (!canConfigureQuota) return;
    setQuotaLoading(true);
    setQuotaError("");
    try {
      const policy = await fetchAdminRegularizationQuotaPolicy();
      setQuotaPolicy(policy);
      setQuotaDraft({
        weekly_limit: String(policy.weekly_limit),
        monthly_limit: String(policy.monthly_limit),
      });
    } catch (loadError) {
      setQuotaError(loadError.message || "Could not load the request limits.");
    } finally {
      setQuotaLoading(false);
    }
  }, [canConfigureQuota]);

  useEffect(() => {
    loadQuotaPolicy();
  }, [loadQuotaPolicy]);

  const saveQuotaPolicy = async (event) => {
    event.preventDefault();
    setQuotaSaving(true);
    setQuotaError("");
    try {
      const saved = await updateAdminRegularizationQuotaPolicy({
        weekly_limit: Number(quotaDraft.weekly_limit),
        monthly_limit: Number(quotaDraft.monthly_limit),
      });
      setQuotaPolicy(saved);
      setQuotaDraft({
        weekly_limit: String(saved.weekly_limit),
        monthly_limit: String(saved.monthly_limit),
      });
      success("Quota settings saved successfully.");
    } catch (saveError) {
      notifyError(saveError, { title: "Quota settings failed", fallback: "Could not save the request limits." });
    } finally {
      setQuotaSaving(false);
    }
  };

  if (!canReview) {
    return <Alert severity="warning">You do not have access to review regularization requests.</Alert>;
  }

  return (
    <Box sx={{ maxWidth: 1400, mx: "auto", p: { xs: 2, md: 4 }, width: "100%" }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 2, mb: 3 }}>
        <Box>
          <Typography variant="h4" fontWeight={750}>Regularization</Typography>
          <Typography variant="body2" color="text.secondary">Review employee attendance correction requests.</Typography>
        </Box>
        <TextField
          select
          size="small"
          label="Status"
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
          sx={{ minWidth: 160 }}
        >
          {["PENDING", "APPROVED", "REJECTED", "ALL"].map((status) => (
            <MenuItem key={status} value={status}>{status}</MenuItem>
          ))}
        </TextField>
      </Box>

      {canConfigureQuota && (
        <Paper component="form" variant="outlined" onSubmit={saveQuotaPolicy} sx={{ p: 2.5, mb: 3 }}>
          <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 2, flexWrap: "wrap", mb: 2 }}>
            <Box>
              <Typography variant="h6" fontWeight={700}>Employee request limits</Typography>
              <Typography variant="body2" color="text.secondary">
                Set how many Regularization requests each employee may submit. Updates apply immediately.
              </Typography>
            </Box>
            <Button type="submit" variant="contained" disabled={quotaLoading || quotaSaving}>
              {quotaSaving ? "Saving…" : "Save limits"}
            </Button>
          </Box>
          {quotaError && <Alert severity="error" sx={{ mb: 2 }}>{quotaError}</Alert>}
          <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 2, maxWidth: 680 }}>
            <TextField
              type="number"
              label="Requests per calendar week"
              value={quotaDraft.weekly_limit}
              onChange={(event) => setQuotaDraft((current) => ({ ...current, weekly_limit: event.target.value }))}
              inputProps={{ min: 0, max: 32767, step: 1 }}
              helperText="Monday through Sunday; enter 0 to disable requests."
              disabled={quotaLoading || quotaSaving}
              required
            />
            <TextField
              type="number"
              label="Requests per calendar month"
              value={quotaDraft.monthly_limit}
              onChange={(event) => setQuotaDraft((current) => ({ ...current, monthly_limit: event.target.value }))}
              inputProps={{ min: 0, max: 32767, step: 1 }}
              helperText="Calendar month; enter 0 to disable requests."
              disabled={quotaLoading || quotaSaving}
              required
            />
          </Box>
          {quotaPolicy && (
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
              Current limits: {quotaPolicy.weekly_limit} per week · {quotaPolicy.monthly_limit} per month
            </Typography>
          )}
        </Paper>
      )}

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      <Paper variant="outlined">
        {loading ? (
          <Box sx={{ display: "flex", justifyContent: "center", p: 5 }}><CircularProgress size={30} /></Box>
        ) : requests.length === 0 ? (
          <Typography color="text.secondary" sx={{ p: 3 }}>No regularization requests found.</Typography>
        ) : (
          <TableContainer>
            <Table sx={{ minWidth: 850 }}>
              <TableHead sx={{ bgcolor: "#f8fafc" }}>
                <TableRow>
                  <TableCell>Employee</TableCell>
                  <TableCell>Attendance period</TableCell>
                  <TableCell>Request type</TableCell>
                  <TableCell>Requested check-in</TableCell>
                  <TableCell>Requested check-out</TableCell>
                  <TableCell>Reason</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell align="right">Action</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {requests.map((request) => (
                  <TableRow key={request.id} hover>
                    <TableCell>
                      <Typography variant="body2" fontWeight={600}>{request.employee_name || request.employee_email}</Typography>
                      <Typography variant="caption" color="text.secondary">{request.employee_email}</Typography>
                    </TableCell>
                    <TableCell>{requestPeriod(request)}</TableCell>
                    <TableCell>{request.period_type || "DAY"}{request.request_type ? ` · ${request.request_type.replaceAll("_", " ")}` : ""}</TableCell>
                    <TableCell>{formatTime(request.requested_check_in)}</TableCell>
                    <TableCell>{formatTime(request.requested_check_out)}</TableCell>
                    <TableCell sx={{ maxWidth: 240 }}><Typography variant="body2" noWrap title={request.reason}>{request.reason}</Typography></TableCell>
                    <TableCell><Chip label={request.status} color={statusColor(request.status)} size="small" /></TableCell>
                    <TableCell align="right">
                      <Button
                        component={Link}
                        to={`/administration/regularization/${request.id}`}
                        size="small"
                        variant={request.status === "PENDING" ? "contained" : "outlined"}
                        sx={{ textTransform: "none" }}
                      >
                        {request.status === "PENDING" ? "Review" : "View"}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>
    </Box>
  );
}
