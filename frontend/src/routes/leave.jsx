import React, { useState, useEffect } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { RequireAuth } from "../components/RequireAuth.jsx";
import {
  Box,
  Typography,
  Paper,
  Button,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
  Grid2,
  FormControl,
  FormLabel,
  RadioGroup,
  FormControlLabel,
  Radio,
  Alert,
  CircularProgress,
  IconButton,
  Tooltip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  LinearProgress,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import EventBusyIcon from "@mui/icons-material/EventBusy";
import BeachAccessIcon from "@mui/icons-material/BeachAccess";
import LocalHospitalIcon from "@mui/icons-material/LocalHospital";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import CancelIcon from "@mui/icons-material/Cancel";
import InfoIcon from "@mui/icons-material/Info";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorIcon from "@mui/icons-material/Error";
import CloseIcon from "@mui/icons-material/Close";
import {
  fetchLeaveBalances,
  fetchLeaveRequests,
  fetchLeaveTypes,
  submitLeaveRequest,
  cancelLeaveRequest,
  estimateLeaveDuration,
} from "../lib/api.js";

export const Route = createFileRoute("/leave")({
  component: Leave,
});

function StatusChip({ status }) {
  let color = "default";
  let icon = null;

  switch (status) {
    case "APPROVED":
      color = "success";
      icon = <CheckCircleIcon fontSize="small" />;
      break;
    case "PENDING":
      color = "warning";
      icon = <AccessTimeIcon fontSize="small" />;
      break;
    case "DENIED":
      color = "error";
      icon = <ErrorIcon fontSize="small" />;
      break;
    case "CANCELLED":
      color = "default";
      icon = <CancelIcon fontSize="small" />;
      break;
    default:
      break;
  }

  return (
    <Chip
      label={status}
      color={color}
      size="small"
      icon={icon}
      sx={{ fontWeight: 600, fontSize: "0.75rem" }}
    />
  );
}

function LeaveBalanceCard({ balance }) {
  const available = balance.available ?? 0;
  const entitlement = balance.annual_entitlement ?? 0;
  const used = balance.used ?? 0;
  const pending = balance.pending ?? 0;
  const carried = balance.carried_forward ?? 0;

  const totalPossible = entitlement + carried;
  const percentage = totalPossible > 0 ? Math.min(100, Math.round((used / totalPossible) * 100)) : 0;

  return (
    <Paper
      sx={{
        p: 2.5,
        borderRadius: 3,
        border: "1px solid",
        borderColor: "divider",
        boxShadow: "0 2px 8px rgba(0,0,0,0.04)",
        display: "flex",
        flexDirection: "column",
        justify: "space-between",
        gap: 1.5,
      }}
    >
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <Box>
          <Typography variant="body2" color="text.secondary" fontWeight={600} sx={{ textTransform: "uppercase", letterSpacing: "0.5px", fontSize: "0.75rem" }}>
            {balance.leave_type_name}
          </Typography>
          <Typography variant="caption" color="text.disabled">
            {balance.leave_type_code} {balance.is_paid ? "• Paid" : "• Unpaid"}
          </Typography>
        </Box>
        <Chip
          label={`${available} Left`}
          color={available > 0 ? "primary" : "default"}
          size="small"
          sx={{ fontWeight: 700, borderRadius: 1.5 }}
        />
      </Box>

      <Box sx={{ my: 0.5 }}>
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", mb: 0.5 }}>
          <Typography variant="h4" fontWeight={700} color="primary.main">
            {available}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            of {totalPossible} days
          </Typography>
        </Box>
        <LinearProgress
          variant="determinate"
          value={percentage}
          sx={{
            height: 6,
            borderRadius: 3,
            bgcolor: "action.hover",
            "& .MuiLinearProgress-bar": { bgcolor: "primary.main", borderRadius: 3 },
          }}
        />
      </Box>

      <Box sx={{ display: "flex", gap: 2, pt: 1, borderTop: "1px solid", borderColor: "divider", fontSize: "0.75rem" }}>
        <Box>
          <Typography variant="caption" color="text.secondary">Used: </Typography>
          <Typography variant="caption" fontWeight={600}>{used}</Typography>
        </Box>
        <Box>
          <Typography variant="caption" color="text.secondary">Pending: </Typography>
          <Typography variant="caption" fontWeight={600} color="warning.main">{pending}</Typography>
        </Box>
        {carried > 0 && (
          <Box>
            <Typography variant="caption" color="text.secondary">Carried: </Typography>
            <Typography variant="caption" fontWeight={600}>{carried}</Typography>
          </Box>
        )}
      </Box>
    </Paper>
  );
}

function Leave() {
  const [balances, setBalances] = useState([]);
  const [requests, setRequests] = useState([]);
  const [leaveTypes, setLeaveTypes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Filter state
  const [statusFilter, setStatusFilter] = useState("ALL");

  // Modal State
  const [openModal, setOpenModal] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);

  // Form Fields
  const [leaveTypeId, setLeaveTypeId] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [dayType, setDayType] = useState("FULL_DAY");
  const [reason, setReason] = useState("");
  const [attachment, setAttachment] = useState("");
  const [estimatedDuration, setEstimatedDuration] = useState(null);
  const [estimating, setEstimating] = useState(false);

  // Remarks modal
  const [remarksModal, setRemarksModal] = useState({ open: false, title: "", text: "" });

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [balData, reqData, typesData] = await Promise.all([
        fetchLeaveBalances(),
        fetchLeaveRequests(),
        fetchLeaveTypes(),
      ]);
      setBalances(balData ?? []);
      setRequests(reqData ?? []);
      setLeaveTypes(typesData ?? []);
    } catch (err) {
      setError(err.message || "Failed to load leave data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Recalculate duration when dates/dayType change
  useEffect(() => {
    if (startDate && endDate) {
      const calc = async () => {
        setEstimating(true);
        try {
          const res = await estimateLeaveDuration(startDate, endDate, dayType);
          setEstimatedDuration(res.duration_days);
        } catch {
          setEstimatedDuration(null);
        } finally {
          setEstimating(false);
        }
      };
      calc();
    } else {
      setEstimatedDuration(null);
    }
  }, [startDate, endDate, dayType]);

  const handleOpenModal = () => {
    setFormError(null);
    setLeaveTypeId(leaveTypes.length > 0 ? leaveTypes[0].id : "");
    const todayStr = new Date().toISOString().split("T")[0];
    setStartDate(todayStr);
    setEndDate(todayStr);
    setDayType("FULL_DAY");
    setReason("");
    setAttachment("");
    setEstimatedDuration(1.0);
    setOpenModal(true);
  };

  const handleCloseModal = () => {
    setOpenModal(false);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError(null);

    if (!leaveTypeId) {
      setFormError("Please select a leave type.");
      return;
    }
    if (!startDate || !endDate) {
      setFormError("Please select start and end dates.");
      return;
    }
    if (!reason.trim()) {
      setFormError("Please provide a reason for the leave request.");
      return;
    }

    setSubmitting(true);
    try {
      await submitLeaveRequest({
        leave_type: leaveTypeId,
        start_date: startDate,
        end_date: endDate,
        day_type: dayType,
        reason: reason.trim(),
        attachment: attachment.trim(),
      });
      setSuccessMsg("Leave request submitted successfully!");
      setOpenModal(false);
      await loadData();
    } catch (err) {
      setFormError(err.message || "Failed to submit leave request.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancelRequest = async (id) => {
    if (!window.confirm("Are you sure you want to cancel this pending leave request?")) return;

    try {
      await cancelLeaveRequest(id);
      setSuccessMsg("Leave request cancelled.");
      await loadData();
    } catch (err) {
      setError(err.message || "Failed to cancel request.");
    }
  };

  const filteredRequests = requests.filter((r) => {
    if (statusFilter === "ALL") return true;
    return r.status === statusFilter;
  });

  const selectedTypeObj = leaveTypes.find((t) => t.id === leaveTypeId);

  return (
    <RequireAuth>
      <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
        {/* Top Bar */}
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 2 }}>
          <Box>
            <Typography variant="h5" sx={{ fontWeight: 700, letterSpacing: "-0.5px" }}>
              Leave Management
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, fontWeight: 500 }}>
              View your leave balances, submit requests, and track approval status.
            </Typography>
          </Box>
          <Button
            variant="contained"
            color="primary"
            startIcon={<AddIcon />}
            onClick={handleOpenModal}
            sx={{ borderRadius: 2, textTransform: "none", fontWeight: 600, px: 2.5 }}
          >
            Apply for Leave
          </Button>
        </Box>

        {/* Global Notifications */}
        {error && (
          <Alert severity="error" onClose={() => setError(null)} sx={{ borderRadius: 2 }}>
            {error}
          </Alert>
        )}
        {successMsg && (
          <Alert severity="success" onClose={() => setSuccessMsg(null)} sx={{ borderRadius: 2 }}>
            {successMsg}
          </Alert>
        )}

        {/* Balances Section */}
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 700, mb: 1.5, letterSpacing: "-0.3px" }}>
            My Leave Balances
          </Typography>
          {loading ? (
            <Box sx={{ display: "flex", p: 4, justifyContent: "center" }}>
              <CircularProgress size={32} />
            </Box>
          ) : balances.length === 0 ? (
            <Paper sx={{ p: 3, borderRadius: 3, border: "1px dashed", borderColor: "divider", textAlign: "center" }}>
              <Typography color="text.secondary">No active leave balances available for your profile.</Typography>
            </Paper>
          ) : (
            <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", md: "repeat(3, 1fr)" }, gap: 2 }}>
              {balances.map((bal) => (
                <LeaveBalanceCard key={bal.leave_type_id} balance={bal} />
              ))}
            </Box>
          )}
        </Box>

        {/* Leave Requests Table */}
        <Paper sx={{ borderRadius: 3, border: "1px solid", borderColor: "divider", boxShadow: "none", overflow: "hidden" }}>
          <Box sx={{ px: 3, py: 2, borderBottom: "1px solid", borderColor: "divider", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 1.5 }}>
            <Typography variant="h6" sx={{ fontWeight: 700, letterSpacing: "-0.3px" }}>
              My Requests
            </Typography>
            <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
              {["ALL", "PENDING", "APPROVED", "DENIED", "CANCELLED"].map((st) => (
                <Chip
                  key={st}
                  label={st === "ALL" ? "All" : st}
                  clickable
                  color={statusFilter === st ? "primary" : "default"}
                  variant={statusFilter === st ? "filled" : "outlined"}
                  onClick={() => setStatusFilter(st)}
                  size="small"
                  sx={{ fontWeight: 600 }}
                />
              ))}
            </Box>
          </Box>

          {loading ? (
            <Box sx={{ display: "flex", p: 6, justifyContent: "center" }}>
              <CircularProgress size={32} />
            </Box>
          ) : filteredRequests.length === 0 ? (
            <Box sx={{ p: 6, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: "text.secondary", gap: 1 }}>
              <EventBusyIcon sx={{ fontSize: 48, color: "action.disabled" }} />
              <Typography variant="body1" fontWeight={600} color="text.primary">
                No leave requests found
              </Typography>
              <Typography variant="body2">
                When you submit a leave request, it will appear here with real-time status updates.
              </Typography>
            </Box>
          ) : (
            <TableContainer>
              <Table sx={{ minWidth: 650 }}>
                <TableHead sx={{ bgcolor: "rgba(0,0,0,0.02)" }}>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 700 }}>Leave Type</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Dates</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Duration</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Day Type</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Reason</TableCell>
                    <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 700 }}>Actions</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredRequests.map((req) => (
                    <TableRow key={req.id} hover>
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>
                          {req.leave_type_name}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          Submitted: {new Date(req.submitted_at).toLocaleDateString()}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontWeight={500}>
                          {req.start_date === req.end_date ? req.start_date : `${req.start_date} → ${req.end_date}`}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>
                          {req.duration_days} {req.duration_days === 1 ? "day" : "days"}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={req.day_type.replace("_", " ")}
                          size="small"
                          variant="outlined"
                          sx={{ fontSize: "0.7rem" }}
                        />
                      </TableCell>
                      <TableCell sx={{ maxWidth: 200 }}>
                        <Typography variant="body2" noWrap title={req.reason}>
                          {req.reason}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <StatusChip status={req.status} />
                      </TableCell>
                      <TableCell align="right">
                        <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 1 }}>
                          {req.reviewer_remarks && (
                            <Tooltip title="View Reviewer Remarks">
                              <IconButton
                                size="small"
                                color="info"
                                onClick={() => setRemarksModal({ open: true, title: `Remarks for ${req.leave_type_name}`, text: req.reviewer_remarks })}
                              >
                                <InfoIcon fontSize="small" />
                              </IconButton>
                            </Tooltip>
                          )}
                          {req.status === "PENDING" && (
                            <Button
                              size="small"
                              color="error"
                              variant="outlined"
                              onClick={() => handleCancelRequest(req.id)}
                              sx={{ borderRadius: 1.5, textTransform: "none", fontSize: "0.75rem", py: 0.3 }}
                            >
                              Cancel
                            </Button>
                          )}
                        </Box>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </Paper>

        {/* Apply Leave Modal */}
        <Dialog open={openModal} onClose={handleCloseModal} maxWidth="sm" fullWidth>
          <DialogTitle sx={{ fontWeight: 700, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            Apply for Leave
            <IconButton size="small" onClick={handleCloseModal}>
              <CloseIcon />
            </IconButton>
          </DialogTitle>
          <form onSubmit={handleSubmit}>
            <DialogContent dividers sx={{ display: "flex", flexDirection: "column", gap: 2.5 }}>
              {formError && <Alert severity="error">{formError}</Alert>}

              <TextField
                select
                fullWidth
                label="Leave Type"
                value={leaveTypeId}
                onChange={(e) => setLeaveTypeId(e.target.value)}
                required
              >
                {leaveTypes.map((t) => (
                  <MenuItem key={t.id} value={t.id}>
                    {t.name} ({t.code}) {t.is_paid ? "" : "• Unpaid"}
                  </MenuItem>
                ))}
              </TextField>

              <Grid2 container spacing={2}>
                <Grid2 size={{ xs: 6 }}>
                  <TextField
                    fullWidth
                    type="date"
                    label="Start Date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    InputLabelProps={{ shrink: true }}
                    required
                  />
                </Grid2>
                <Grid2 size={{ xs: 6 }}>
                  <TextField
                    fullWidth
                    type="date"
                    label="End Date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    InputLabelProps={{ shrink: true }}
                    required
                  />
                </Grid2>
              </Grid2>

              <FormControl component="fieldset">
                <FormLabel component="legend" sx={{ fontSize: "0.85rem", fontWeight: 600 }}>
                  Day Type
                </FormLabel>
                <RadioGroup
                  row
                  value={dayType}
                  onChange={(e) => setDayType(e.target.value)}
                >
                  <FormControlLabel value="FULL_DAY" control={<Radio size="small" />} label="Full Day" />
                  <FormControlLabel
                    value="FIRST_HALF"
                    control={<Radio size="small" />}
                    label="First Half (0.5)"
                    disabled={startDate !== endDate || selectedTypeObj?.allow_half_day === false}
                  />
                  <FormControlLabel
                    value="SECOND_HALF"
                    control={<Radio size="small" />}
                    label="Second Half (0.5)"
                    disabled={startDate !== endDate || selectedTypeObj?.allow_half_day === false}
                  />
                </RadioGroup>
              </FormControl>

              {/* Estimated Duration Preview */}
              <Box sx={{ p: 2, borderRadius: 2, bgcolor: "rgba(125, 37, 169, 0.05)", border: "1px solid", borderColor: "rgba(125, 37, 169, 0.2)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <Typography variant="body2" fontWeight={600} color="text.secondary">
                  Estimated Working Duration:
                </Typography>
                <Typography variant="body1" fontWeight={700} color="primary.main">
                  {estimating ? <CircularProgress size={16} /> : estimatedDuration !== null ? `${estimatedDuration} working day(s)` : "--"}
                </Typography>
              </Box>

              <TextField
                fullWidth
                multiline
                rows={3}
                label="Reason for Leave"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Explain the reason for requesting leave..."
                required
              />

              <TextField
                fullWidth
                label="Supporting Document / Link (Optional)"
                value={attachment}
                onChange={(e) => setAttachment(e.target.value)}
                placeholder="Attach document URL or notes if required..."
              />
            </DialogContent>
            <DialogActions sx={{ px: 3, py: 2 }}>
              <Button onClick={handleCloseModal} color="inherit">
                Cancel
              </Button>
              <Button type="submit" variant="contained" color="primary" disabled={submitting}>
                {submitting ? <CircularProgress size={24} /> : "Submit Request"}
              </Button>
            </DialogActions>
          </form>
        </Dialog>

        {/* Remarks Modal */}
        <Dialog open={remarksModal.open} onClose={() => setRemarksModal({ open: false, title: "", text: "" })} maxWidth="xs" fullWidth>
          <DialogTitle sx={{ fontWeight: 700 }}>{remarksModal.title}</DialogTitle>
          <DialogContent dividers>
            <Typography variant="body1">{remarksModal.text}</Typography>
          </DialogContent>
          <DialogActions>
            <Button onClick={() => setRemarksModal({ open: false, title: "", text: "" })}>Close</Button>
          </DialogActions>
        </Dialog>
      </Box>
    </RequireAuth>
  );
}
