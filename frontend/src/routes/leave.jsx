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
import AttachFileIcon from "@mui/icons-material/AttachFile";
import AttachmentIcon from "@mui/icons-material/Attachment";
import CloseIcon from "@mui/icons-material/Close";
import EventBusyIcon from "@mui/icons-material/EventBusy";
import BeachAccessIcon from "@mui/icons-material/BeachAccess";
import LocalHospitalIcon from "@mui/icons-material/LocalHospital";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import CancelIcon from "@mui/icons-material/Cancel";
import InfoIcon from "@mui/icons-material/Info";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorIcon from "@mui/icons-material/Error";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import DownloadIcon from "@mui/icons-material/Download";
import FullscreenIcon from "@mui/icons-material/Fullscreen";
import {
  apiRequest,
  fetchLeaveBalances,
  fetchLeaveRequests,
  fetchLeaveTypes,
  submitLeaveRequest,
  uploadFile,
  cancelLeaveRequest,
  estimateLeaveDuration,
} from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";
import { filterScopedRecords, useOrganizationScope } from "../lib/organizationScope.jsx";

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
          <Box sx={{ textAlign: "right" }}>
            <Typography variant="body2" color="text.secondary">
              of {totalPossible} days
            </Typography>
            {entitlement > 0 && entitlement >= 12 && (
              <Typography variant="caption" color="text.disabled" sx={{ display: "block", mt: -0.5 }}>
                ≈ {Math.round(entitlement / 12)} days per month
              </Typography>
            )}
          </Box>
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
  const { loginType } = useAuth();
  const { selectedScope } = useOrganizationScope();
  const today = new Date();
  const todayDateString = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;

  const [balances, setBalances] = useState([]);
  const [requests, setRequests] = useState([]);
  const [employees, setEmployees] = useState([]);
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
  const [attachmentFile, setAttachmentFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [estimatedDuration, setEstimatedDuration] = useState(null);
  const [estimating, setEstimating] = useState(false);

  // Remarks modal
  const [remarksModal, setRemarksModal] = useState({ open: false, title: "", text: "" });
  
  // Document preview modal
  const [documentModal, setDocumentModal] = useState({ open: false, url: "", title: "", fileName: "" });

  const handleDownloadFile = (url, fileName) => {
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName || 'document';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const getFileExtension = (url) => {
    return url.split('.').pop().toLowerCase();
  };

  const isImageFile = (url) => {
    const imageExtensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'];
    return imageExtensions.includes(getFileExtension(url));
  };

  const isPdfFile = (url) => {
    return getFileExtension(url) === 'pdf';
  };

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

  useEffect(() => {
    if (loginType !== "systemadmin") return;
    apiRequest("/admin/employees/list/").then((data) => setEmployees(Array.isArray(data) ? data : [])).catch(() => setEmployees([]));
  }, [loginType]);

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
    setStartDate(todayDateString);
    setEndDate(todayDateString);
    setDayType("FULL_DAY");
    setReason("");
    setAttachment("");
    setAttachmentFile(null);
    setEstimatedDuration(1.0);
    setOpenModal(true);
  };

  const handleCloseModal = () => {
    setOpenModal(false);
  };

  const handleFileChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      // Validate file size (5MB limit)
      if (file.size > 5 * 1024 * 1024) {
        setFormError("File size must be less than 5MB.");
        return;
      }
      
      // Validate file type
      const allowedTypes = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx'];
      const fileExtension = '.' + file.name.split('.').pop().toLowerCase();
      if (!allowedTypes.includes(fileExtension)) {
        setFormError("File type not allowed. Please upload PDF, JPG, PNG, DOC, or DOCX files.");
        return;
      }
      
      setAttachmentFile(file);
      setFormError(null);
    }
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

    // Check if document is required for selected leave type
    const selectedType = leaveTypes.find(t => t.id === leaveTypeId);
    const selectedBalance = balances.find(b => b.leave_type_id === leaveTypeId);
    const requiresDocument = selectedType?.requires_document || selectedBalance?.requires_document;
    
    if (requiresDocument && !attachment.trim() && !attachmentFile) {
      setFormError("Supporting document is required for this leave type.");
      return;
    }

    setSubmitting(true);
    try {
      let attachmentUrl = attachment.trim();
      
      // Upload file if provided
      if (attachmentFile) {
        setUploading(true);
        try {
          const uploadResponse = await uploadFile(attachmentFile);
          attachmentUrl = uploadResponse.file_url;
        } catch (uploadError) {
          setFormError(uploadError.message || "Failed to upload file.");
          return;
        } finally {
          setUploading(false);
        }
      }

      await submitLeaveRequest({
        leave_type: leaveTypeId,
        start_date: startDate,
        end_date: endDate,
        day_type: dayType,
        reason: reason.trim(),
        attachment: attachmentUrl,
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

  const scopedRequests = loginType === "systemadmin" && (selectedScope.sectionId || selectedScope.subsectionId)
    ? requests.filter((request) => {
      const employee = employees.find((item) => item.email === request.employee_email);
      return employee && filterScopedRecords([employee], selectedScope).length > 0;
    })
    : requests;
  const filteredRequests = scopedRequests.filter((r) => {
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
                    <TableCell sx={{ fontWeight: 700 }}>Attachment</TableCell>
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
                        {req.attachment ? (
                          <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                            <AttachmentIcon fontSize="small" color="primary" />
                            <Button
                              size="small"
                              variant="text"
                              color="primary"
                              onClick={() => {
                                if (req.attachment.startsWith('http')) {
                                  setDocumentModal({
                                    open: true,
                                    url: req.attachment,
                                    title: `Document for ${req.leave_type_name} Leave`,
                                    fileName: req.attachment.split('/').pop() || 'document'
                                  });
                                } else {
                                  const baseUrl = import.meta.env.VITE_API_BASE_URL?.replace('/api', '') || 'http://127.0.0.1:8000';
                                  const fullUrl = req.attachment.startsWith('/') ? 
                                    `${baseUrl}${req.attachment}` : 
                                    req.attachment;
                                  setDocumentModal({
                                    open: true,
                                    url: fullUrl,
                                    title: `Document for ${req.leave_type_name} Leave`,
                                    fileName: req.attachment.split('/').pop() || 'document'
                                  });
                                }
                              }}
                              sx={{ 
                                p: 0, 
                                minWidth: 'auto', 
                                textTransform: 'none',
                                fontSize: '0.7rem'
                              }}
                            >
                              View Document
                            </Button>
                          </Box>
                        ) : (
                          <Typography variant="caption" color="text.disabled">
                            No attachment
                          </Typography>
                        )}
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
                    onChange={(e) => {
                      const nextStartDate = e.target.value < todayDateString ? todayDateString : e.target.value;
                      setStartDate(nextStartDate);
                      if (!endDate || endDate < nextStartDate) {
                        setEndDate(nextStartDate);
                      }
                    }}
                    InputLabelProps={{ shrink: true }}
                    inputProps={{ min: todayDateString }}
                    required
                  />
                </Grid2>
                <Grid2 size={{ xs: 6 }}>
                  <TextField
                    fullWidth
                    type="date"
                    label="End Date"
                    value={endDate}
                    onChange={(e) => {
                      const minimumEndDate = startDate || todayDateString;
                      setEndDate(e.target.value < minimumEndDate ? minimumEndDate : e.target.value);
                    }}
                    InputLabelProps={{ shrink: true }}
                    inputProps={{ min: startDate || todayDateString }}
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

              {/* Supporting Document Section */}
              <Box>
                {(() => {
                  const selectedType = leaveTypes.find(t => t.id === leaveTypeId);
                  const selectedBalance = balances.find(b => b.leave_type_id === leaveTypeId);
                  const requiresDocument = selectedType?.requires_document || selectedBalance?.requires_document;
                  
                  return (
                    <>
                      <Typography variant="body2" fontWeight={600} sx={{ mb: 1 }}>
                        Supporting Document {requiresDocument ? "(Required)" : "(Optional)"}
                      </Typography>
                      
                      {/* File Upload */}
                      <Box sx={{ mb: 2 }}>
                        <input
                          accept=".pdf,.jpg,.jpeg,.png,.doc,.docx"
                          style={{ display: 'none' }}
                          id="attachment-file-input"
                          type="file"
                          onChange={handleFileChange}
                        />
                        <label htmlFor="attachment-file-input">
                          <Button
                            variant="outlined"
                            component="span"
                            startIcon={<AttachFileIcon />}
                            disabled={uploading}
                            sx={{ mr: 1 }}
                          >
                            Choose File
                          </Button>
                        </label>
                        {attachmentFile && (
                          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                            Selected: {attachmentFile.name}
                          </Typography>
                        )}
                      </Box>
                      
                      {/* URL Input as alternative */}
                      <TextField
                        fullWidth
                        label="Or enter document URL/link"
                        value={attachment}
                        onChange={(e) => setAttachment(e.target.value)}
                        placeholder="Enter document URL or notes..."
                        size="small"
                      />
                      
                      {requiresDocument && (
                        <Typography variant="caption" color="warning.main" sx={{ mt: 0.5, display: 'block' }}>
                          This leave type requires supporting documentation.
                        </Typography>
                      )}
                    </>
                  );
                })()}
              </Box>
            </DialogContent>
            <DialogActions sx={{ px: 3, py: 2 }}>
              <Button onClick={handleCloseModal} color="inherit">
                Cancel
              </Button>
              <Button type="submit" variant="contained" color="primary" disabled={submitting || uploading}>
                {uploading ? (
                  <>
                    <CircularProgress size={16} sx={{ mr: 1 }} />
                    Uploading...
                  </>
                ) : submitting ? (
                  <>
                    <CircularProgress size={16} sx={{ mr: 1 }} />
                    Submitting...
                  </>
                ) : (
                  "Submit Request"
                )}
              </Button>
            </DialogActions>
          </form>
        </Dialog>

        {/* Document Preview Modal */}
        <Dialog 
          open={documentModal.open} 
          onClose={() => setDocumentModal({ open: false, url: "", title: "", fileName: "" })} 
          maxWidth="lg" 
          fullWidth
          PaperProps={{
            sx: { height: '90vh', maxHeight: '90vh' }
          }}
        >
          <DialogTitle sx={{ 
            fontWeight: 700, 
            display: "flex", 
            justifyContent: "space-between", 
            alignItems: "center",
            borderBottom: 1,
            borderColor: 'divider'
          }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <AttachmentIcon color="primary" />
              <Typography variant="h6" component="span">
                {documentModal.title}
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Tooltip title="Download Document">
                <IconButton 
                  size="small" 
                  color="primary"
                  onClick={() => handleDownloadFile(documentModal.url, documentModal.fileName)}
                >
                  <DownloadIcon />
                </IconButton>
              </Tooltip>
              <Tooltip title="Open in New Tab">
                <IconButton 
                  size="small" 
                  color="primary"
                  onClick={() => window.open(documentModal.url, '_blank')}
                >
                  <OpenInNewIcon />
                </IconButton>
              </Tooltip>
              <Tooltip title="Fullscreen">
                <IconButton 
                  size="small" 
                  color="primary"
                  onClick={() => {
                    const elem = document.querySelector('[data-document-preview]');
                    if (elem && elem.requestFullscreen) {
                      elem.requestFullscreen();
                    }
                  }}
                >
                  <FullscreenIcon />
                </IconButton>
              </Tooltip>
              <IconButton size="small" onClick={() => setDocumentModal({ open: false, url: "", title: "", fileName: "" })}>
                <CloseIcon />
              </IconButton>
            </Box>
          </DialogTitle>
          <DialogContent sx={{ p: 0, display: 'flex', flexDirection: 'column', height: '100%' }}>
            {documentModal.url && (
              <Box 
                sx={{ 
                  flex: 1, 
                  display: 'flex', 
                  flexDirection: 'column',
                  backgroundColor: '#f5f5f5',
                  position: 'relative'
                }}
                data-document-preview
              >
                {isImageFile(documentModal.url) ? (
                  <Box sx={{ 
                    flex: 1, 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'center',
                    p: 2
                  }}>
                    <img
                      src={documentModal.url}
                      alt="Document preview"
                      style={{ 
                        maxWidth: '100%', 
                        maxHeight: '100%',
                        objectFit: 'contain',
                        borderRadius: '8px',
                        boxShadow: '0 4px 12px rgba(0,0,0,0.15)'
                      }}
                      onError={(e) => {
                        e.target.style.display = 'none';
                        e.target.nextElementSibling.style.display = 'flex';
                      }}
                    />
                    <Box sx={{ 
                      display: 'none', 
                      flexDirection: 'column', 
                      alignItems: 'center', 
                      gap: 2,
                      p: 4,
                      textAlign: 'center'
                    }}>
                      <ErrorIcon sx={{ fontSize: 48, color: 'text.disabled' }} />
                      <Typography variant="body1" color="text.secondary">
                        Unable to preview this image
                      </Typography>
                    </Box>
                  </Box>
                ) : isPdfFile(documentModal.url) ? (
                  <iframe
                    src={`${documentModal.url}#toolbar=1&navpanes=1&scrollbar=1`}
                    width="100%"
                    height="100%"
                    style={{ border: 'none', flex: 1 }}
                    title="PDF Preview"
                    onError={() => {
                      console.log('PDF preview failed');
                    }}
                  />
                ) : (
                  <Box sx={{ 
                    flex: 1, 
                    display: 'flex', 
                    flexDirection: 'column', 
                    alignItems: 'center', 
                    justifyContent: 'center',
                    gap: 2,
                    p: 4,
                    textAlign: 'center'
                  }}>
                    <AttachmentIcon sx={{ fontSize: 64, color: 'primary.main' }} />
                    <Typography variant="h6" color="text.primary">
                      {documentModal.fileName}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Preview not available for this file type
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 2, mt: 2 }}>
                      <Button
                        variant="contained"
                        startIcon={<DownloadIcon />}
                        onClick={() => handleDownloadFile(documentModal.url, documentModal.fileName)}
                      >
                        Download File
                      </Button>
                      <Button
                        variant="outlined"
                        startIcon={<OpenInNewIcon />}
                        onClick={() => window.open(documentModal.url, '_blank')}
                      >
                        Open in Browser
                      </Button>
                    </Box>
                  </Box>
                )}
              </Box>
            )}
          </DialogContent>
          <DialogActions sx={{ 
            borderTop: 1, 
            borderColor: 'divider',
            p: 2,
            backgroundColor: 'grey.50'
          }}>
            <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
              File: {documentModal.fileName}
            </Typography>
            <Button 
              onClick={() => handleDownloadFile(documentModal.url, documentModal.fileName)}
              variant="contained"
              startIcon={<DownloadIcon />}
              sx={{ mr: 1 }}
            >
              Download
            </Button>
            <Button 
              onClick={() => window.open(documentModal.url, '_blank')}
              variant="outlined"
              startIcon={<OpenInNewIcon />}
              sx={{ mr: 1 }}
            >
              Open in New Tab
            </Button>
            <Button onClick={() => setDocumentModal({ open: false, url: "", title: "", fileName: "" })}>
              Close
            </Button>
          </DialogActions>
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
