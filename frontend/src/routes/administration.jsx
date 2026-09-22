import React, { useState, useEffect } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { RequireAuth } from "../components/RequireAuth.jsx";
import { useAuth } from "../lib/auth.jsx";
import {
  Box,
  Typography,
  Paper,
  Tabs,
  Tab,
  Button,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Alert,
  CircularProgress,
  IconButton,
  Tooltip,
  Switch,
  FormControlLabel,
  Grid2,
} from "@mui/material";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import CancelIcon from "@mui/icons-material/Cancel";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import ErrorIcon from "@mui/icons-material/Error";
import AddIcon from "@mui/icons-material/Add";
import EditIcon from "@mui/icons-material/Edit";
import CloseIcon from "@mui/icons-material/Close";
import InfoIcon from "@mui/icons-material/Info";
import {
  fetchAdminLeaveRequests,
  approveLeaveRequest,
  denyLeaveRequest,
  cancelApprovedLeaveRequest,
  fetchAdminLeaveBalances,
  fetchLeaveTypesAll,
  createLeaveType,
  updateLeaveType,
  fetchLeavePoliciesAll,
  createLeavePolicy,
  updateLeavePolicy,
} from "../lib/api.js";

export const Route = createFileRoute("/administration")({
  component: Administration,
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

function Administration() {
  const { user, loginType } = useAuth();
  const isSuperUser = Boolean(user?.is_superuser || loginType === "admin");
  const isStaff = Boolean(user?.is_staff || isSuperUser);

  const [currentTab, setCurrentTab] = useState(0);

  // General Notification state
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // ---------------------------------------------------------------------------
  // TAB 0: LEAVE REQUESTS STATE
  // ---------------------------------------------------------------------------
  const [requests, setRequests] = useState([]);
  const [loadingRequests, setLoadingRequests] = useState(false);
  const [statusFilter, setStatusFilter] = useState("PENDING");

  // Approve/Deny Modal state
  const [actionModal, setActionModal] = useState({ open: false, type: "", request: null, remarks: "" });
  const [actionSubmitting, setActionSubmitting] = useState(false);
  const [actionError, setActionError] = useState(null);

  const loadLeaveRequests = async () => {
    setLoadingRequests(true);
    try {
      const params = statusFilter !== "ALL" ? { status: statusFilter } : {};
      const data = await fetchAdminLeaveRequests(params);
      setRequests(data ?? []);
    } catch (err) {
      setError(err.message || "Failed to load leave requests.");
    } finally {
      setLoadingRequests(false);
    }
  };

  useEffect(() => {
    if (isStaff && currentTab === 0) {
      loadLeaveRequests();
    }
  }, [currentTab, statusFilter, isStaff]);

  const handleOpenAction = (req, type) => {
    setActionError(null);
    setActionModal({ open: true, type, request: req, remarks: "" });
  };

  const handleCloseAction = () => {
    setActionModal({ open: false, type: "", request: null, remarks: "" });
  };

  const handleExecuteAction = async () => {
    setActionError(null);
    const { type, request: req, remarks } = actionModal;

    if (type === "DENY" && !remarks.trim()) {
      setActionError("Reviewer remarks are required when denying a leave request.");
      return;
    }

    setActionSubmitting(true);
    try {
      if (type === "APPROVE") {
        await approveLeaveRequest(req.id, remarks.trim());
        setSuccessMsg(`Approved leave request for ${req.employee_email}`);
      } else if (type === "DENY") {
        await denyLeaveRequest(req.id, remarks.trim());
        setSuccessMsg(`Denied leave request for ${req.employee_email}`);
      } else if (type === "CANCEL") {
        await cancelApprovedLeaveRequest(req.id);
        setSuccessMsg(`Cancelled approved leave request for ${req.employee_email}`);
      }
      handleCloseAction();
      await loadLeaveRequests();
    } catch (err) {
      setActionError(err.message || "Action failed.");
    } finally {
      setActionSubmitting(false);
    }
  };

  // ---------------------------------------------------------------------------
  // TAB 1: LEAVE POLICIES STATE (Super Admin)
  // ---------------------------------------------------------------------------
  const [policies, setPolicies] = useState([]);
  const [allTypes, setAllTypes] = useState([]);
  const [loadingPolicies, setLoadingPolicies] = useState(false);
  const [policyTypeFilter, setPolicyTypeFilter] = useState("PERMANENT");

  // Policy Modal
  const [policyModal, setPolicyModal] = useState({ open: false, policy: null });
  const [policySubmitting, setPolicySubmitting] = useState(false);
  const [policyError, setPolicyError] = useState(null);

  // Policy Form Fields
  const [polEmployeeType, setPolEmployeeType] = useState("PERMANENT");
  const [polLeaveTypeId, setPolLeaveTypeId] = useState("");
  const [polEntitlement, setPolEntitlement] = useState(12);
  const [polCarryForward, setPolCarryForward] = useState(false);
  const [polMaxCarryForward, setPolMaxCarryForward] = useState(0);
  const [polMaxConsecutive, setPolMaxConsecutive] = useState(10);
  const [polMinNotice, setPolMinNotice] = useState(0);
  const [polAllowHalfDay, setPolAllowHalfDay] = useState(true);
  const [polReqDoc, setPolReqDoc] = useState(false);
  const [polEffectiveFrom, setPolEffectiveFrom] = useState(new Date().toISOString().split("T")[0]);
  const [polIsActive, setPolIsActive] = useState(true);

  const loadPoliciesAndTypes = async () => {
    setLoadingPolicies(true);
    try {
      const [pData, tData] = await Promise.all([
        fetchLeavePoliciesAll(),
        fetchLeaveTypesAll(),
      ]);
      setPolicies(pData ?? []);
      setAllTypes(tData ?? []);
    } catch (err) {
      setError(err.message || "Failed to load policy configurations.");
    } finally {
      setLoadingPolicies(false);
    }
  };

  useEffect(() => {
    if (isSuperUser && currentTab === 1) {
      loadPoliciesAndTypes();
    }
  }, [currentTab, isSuperUser]);

  const handleOpenPolicyModal = (policy = null) => {
    setPolicyError(null);
    if (policy) {
      setPolEmployeeType(policy.employee_type);
      setPolLeaveTypeId(policy.leave_type);
      setPolEntitlement(policy.annual_entitlement);
      setPolCarryForward(policy.allow_carry_forward);
      setPolMaxCarryForward(policy.max_carry_forward);
      setPolMaxConsecutive(policy.max_consecutive_days);
      setPolMinNotice(policy.min_notice_days);
      setPolAllowHalfDay(policy.allow_half_day);
      setPolReqDoc(policy.requires_document);
      setPolEffectiveFrom(policy.effective_from);
      setPolIsActive(policy.is_active);
      setPolicyModal({ open: true, policy });
    } else {
      setPolEmployeeType(policyTypeFilter);
      setPolLeaveTypeId(allTypes.length > 0 ? allTypes[0].id : "");
      setPolEntitlement(12);
      setPolCarryForward(false);
      setPolMaxCarryForward(0);
      setPolMaxConsecutive(10);
      setPolMinNotice(0);
      setPolAllowHalfDay(true);
      setPolReqDoc(false);
      setPolEffectiveFrom(new Date().toISOString().split("T")[0]);
      setPolIsActive(true);
      setPolicyModal({ open: true, policy: null });
    }
  };

  const handleSavePolicy = async (e) => {
    e.preventDefault();
    setPolicyError(null);
    setPolicySubmitting(true);

    const payload = {
      employee_type: polEmployeeType,
      leave_type: polLeaveTypeId,
      annual_entitlement: polEntitlement,
      allow_carry_forward: polCarryForward,
      max_carry_forward: polMaxCarryForward,
      max_consecutive_days: polMaxConsecutive,
      min_notice_days: polMinNotice,
      allow_half_day: polAllowHalfDay,
      requires_document: polReqDoc,
      effective_from: polEffectiveFrom,
      is_active: polIsActive,
    };

    try {
      if (policyModal.policy) {
        await updateLeavePolicy(policyModal.policy.id, payload);
        setSuccessMsg("Leave policy updated successfully.");
      } else {
        await createLeavePolicy(payload);
        setSuccessMsg("New leave policy created successfully.");
      }
      setPolicyModal({ open: false, policy: null });
      await loadPoliciesAndTypes();
    } catch (err) {
      setPolicyError(err.message || "Failed to save leave policy.");
    } finally {
      setPolicySubmitting(false);
    }
  };

  // ---------------------------------------------------------------------------
  // TAB 2: LEAVE TYPES STATE (Super Admin)
  // ---------------------------------------------------------------------------
  const [typeModal, setTypeModal] = useState({ open: false, typeObj: null });
  const [typeSubmitting, setTypeSubmitting] = useState(false);
  const [typeError, setTypeError] = useState(null);

  const [typeName, setTypeName] = useState("");
  const [typeCode, setTypeCode] = useState("");
  const [typeDesc, setTypeDesc] = useState("");
  const [typePaid, setTypePaid] = useState(true);
  const [typeHalfDay, setTypeHalfDay] = useState(true);
  const [typePastDates, setTypePastDates] = useState(true);
  const [typeFutureDates, setTypeFutureDates] = useState(true);
  const [typeNotice, setTypeNotice] = useState(0);
  const [typeReqDoc, setTypeReqDoc] = useState(false);
  const [typeActive, setTypeActive] = useState(true);

  useEffect(() => {
    if (isSuperUser && currentTab === 2) {
      loadPoliciesAndTypes();
    }
  }, [currentTab, isSuperUser]);

  const handleOpenTypeModal = (typeObj = null) => {
    setTypeError(null);
    if (typeObj) {
      setTypeName(typeObj.name);
      setTypeCode(typeObj.code);
      setTypeDesc(typeObj.description ?? "");
      setTypePaid(typeObj.is_paid);
      setTypeHalfDay(typeObj.allow_half_day);
      setTypePastDates(typeObj.allow_past_dates);
      setTypeFutureDates(typeObj.allow_future_dates);
      setTypeNotice(typeObj.min_notice_days);
      setTypeReqDoc(typeObj.requires_document);
      setTypeActive(typeObj.is_active);
      setTypeModal({ open: true, typeObj });
    } else {
      setTypeName("");
      setTypeCode("");
      setTypeDesc("");
      setTypePaid(true);
      setTypeHalfDay(true);
      setTypePastDates(true);
      setTypeFutureDates(true);
      setTypeNotice(0);
      setTypeReqDoc(false);
      setTypeActive(true);
      setTypeModal({ open: true, typeObj: null });
    }
  };

  const handleSaveType = async (e) => {
    e.preventDefault();
    setTypeError(null);
    setTypeSubmitting(true);

    const payload = {
      name: typeName.trim(),
      code: typeCode.trim().toUpperCase(),
      description: typeDesc.trim(),
      is_paid: typePaid,
      allow_half_day: typeHalfDay,
      allow_past_dates: typePastDates,
      allow_future_dates: typeFutureDates,
      min_notice_days: typeNotice,
      requires_document: typeReqDoc,
      is_active: typeActive,
    };

    try {
      if (typeModal.typeObj) {
        await updateLeaveType(typeModal.typeObj.id, payload);
        setSuccessMsg("Leave type updated successfully.");
      } else {
        await createLeaveType(payload);
        setSuccessMsg("New leave type created successfully.");
      }
      setTypeModal({ open: false, typeObj: null });
      await loadPoliciesAndTypes();
    } catch (err) {
      setTypeError(err.message || "Failed to save leave type.");
    } finally {
      setTypeSubmitting(false);
    }
  };

  // ---------------------------------------------------------------------------
  // TAB 3: EMPLOYEE BALANCES OVERVIEW
  // ---------------------------------------------------------------------------
  const [adminBalances, setAdminBalances] = useState([]);
  const [loadingAdminBalances, setLoadingAdminBalances] = useState(false);
  const [searchEmp, setSearchEmp] = useState("");

  const loadAdminBalances = async () => {
    setLoadingAdminBalances(true);
    try {
      const data = await fetchAdminLeaveBalances();
      setAdminBalances(data ?? []);
    } catch (err) {
      setError(err.message || "Failed to load employee balances.");
    } finally {
      setLoadingAdminBalances(false);
    }
  };

  useEffect(() => {
    if (isStaff && currentTab === 3) {
      loadAdminBalances();
    }
  }, [currentTab, isStaff]);

  if (!isStaff) {
    return (
      <RequireAuth>
        <Box sx={{ p: 4, textAlign: "center", bgcolor: "white", borderRadius: 4, border: "1px solid", borderColor: "divider" }}>
          <Typography variant="h5" fontWeight={600} gutterBottom color="error">
            Access Denied
          </Typography>
          <Typography color="text.secondary">
            You do not have administrative permissions to view this page.
          </Typography>
        </Box>
      </RequireAuth>
    );
  }

  const filteredPolicies = policies.filter((p) => p.employee_type === policyTypeFilter);
  const filteredBalances = adminBalances.filter((b) =>
    b.employee_email.toLowerCase().includes(searchEmp.toLowerCase())
  );

  return (
    <RequireAuth>
      <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
        {/* Header */}
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 700, letterSpacing: "-0.5px" }}>
            Administration & Leave Policy Engine
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Manage employee leave requests, configure rule policies per employee tier, and audit system balances.
          </Typography>
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

        {/* Navigation Tabs */}
        <Paper sx={{ borderRadius: 3, border: "1px solid", borderColor: "divider", boxShadow: "none" }}>
          <Tabs
            value={currentTab}
            onChange={(e, val) => setCurrentTab(val)}
            sx={{ borderBottom: "1px solid", borderColor: "divider", px: 2 }}
          >
            <Tab label="Leave Requests" sx={{ fontWeight: 600, textTransform: "none" }} />
            {isSuperUser && <Tab label="Leave Policies (Super Admin)" sx={{ fontWeight: 600, textTransform: "none" }} />}
            {isSuperUser && <Tab label="Leave Types (Super Admin)" sx={{ fontWeight: 600, textTransform: "none" }} />}
            <Tab label="Employee Balances Overview" sx={{ fontWeight: 600, textTransform: "none" }} />
          </Tabs>

          {/* TAB 0: LEAVE REQUESTS */}
          {currentTab === 0 && (
            <Box sx={{ p: 3 }}>
              <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2, flexWrap: "wrap", gap: 1.5 }}>
                <Typography variant="h6" fontWeight={700}>
                  Employee Leave Requests
                </Typography>
                <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
                  {["PENDING", "APPROVED", "DENIED", "CANCELLED", "ALL"].map((st) => (
                    <Chip
                      key={st}
                      label={st}
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

              {loadingRequests ? (
                <Box sx={{ display: "flex", p: 6, justifyContent: "center" }}>
                  <CircularProgress size={32} />
                </Box>
              ) : requests.length === 0 ? (
                <Box sx={{ p: 6, textAlign: "center", color: "text.secondary" }}>
                  <Typography variant="body1" fontWeight={600} color="text.primary">
                    No requests found matching filter '{statusFilter}'
                  </Typography>
                </Box>
              ) : (
                <TableContainer>
                  <Table sx={{ minWidth: 700 }}>
                    <TableHead sx={{ bgcolor: "rgba(0,0,0,0.02)" }}>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 700 }}>Employee</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Leave Type</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Dates & Duration</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Reason</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                        <TableCell align="right" sx={{ fontWeight: 700 }}>Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {requests.map((req) => (
                        <TableRow key={req.id} hover>
                          <TableCell>
                            <Typography variant="body2" fontWeight={600}>
                              {req.employee_name}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {req.employee_email} • {req.employment_type} ({req.employee_department})
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip label={req.leave_type_name} size="small" variant="outlined" sx={{ fontWeight: 600 }} />
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" fontWeight={600}>
                              {req.start_date === req.end_date ? req.start_date : `${req.start_date} → ${req.end_date}`}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {req.duration_days} day(s) • {req.day_type.replace("_", " ")}
                            </Typography>
                          </TableCell>
                          <TableCell sx={{ maxWidth: 220 }}>
                            <Typography variant="body2" noWrap title={req.reason}>
                              {req.reason}
                            </Typography>
                            {req.attachment && (
                              <Typography variant="caption" color="primary.main" display="block">
                                Doc: {req.attachment}
                              </Typography>
                            )}
                          </TableCell>
                          <TableCell>
                            <StatusChip status={req.status} />
                            {req.reviewer_remarks && (
                              <Typography variant="caption" color="text.secondary" display="block" title={req.reviewer_remarks}>
                                Remarks: {req.reviewer_remarks}
                              </Typography>
                            )}
                          </TableCell>
                          <TableCell align="right">
                            <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 1 }}>
                              {req.status === "PENDING" && (
                                <>
                                  <Button
                                    size="small"
                                    variant="contained"
                                    color="success"
                                    onClick={() => handleOpenAction(req, "APPROVE")}
                                    sx={{ borderRadius: 1.5, textTransform: "none", fontSize: "0.75rem" }}
                                  >
                                    Approve
                                  </Button>
                                  <Button
                                    size="small"
                                    variant="contained"
                                    color="error"
                                    onClick={() => handleOpenAction(req, "DENY")}
                                    sx={{ borderRadius: 1.5, textTransform: "none", fontSize: "0.75rem" }}
                                  >
                                    Deny
                                  </Button>
                                </>
                              )}
                              {req.status === "APPROVED" && (
                                <Button
                                  size="small"
                                  variant="outlined"
                                  color="warning"
                                  onClick={() => handleOpenAction(req, "CANCEL")}
                                  sx={{ borderRadius: 1.5, textTransform: "none", fontSize: "0.75rem" }}
                                >
                                  Cancel Approved
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
            </Box>
          )}

          {/* TAB 1: LEAVE POLICIES (Super Admin) */}
          {isSuperUser && currentTab === 1 && (
            <Box sx={{ p: 3 }}>
              <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2.5, flexWrap: "wrap", gap: 1.5 }}>
                <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
                  <Typography variant="h6" fontWeight={700} sx={{ mr: 1 }}>
                    Leave Policy Rules per Employee Tier:
                  </Typography>
                  {["PERMANENT", "CONTRACT", "INTERN"].map((tier) => (
                    <Chip
                      key={tier}
                      label={tier}
                      clickable
                      color={policyTypeFilter === tier ? "primary" : "default"}
                      onClick={() => setPolicyTypeFilter(tier)}
                      sx={{ fontWeight: 700 }}
                    />
                  ))}
                </Box>
                <Button
                  variant="contained"
                  color="primary"
                  startIcon={<AddIcon />}
                  onClick={() => handleOpenPolicyModal(null)}
                  sx={{ borderRadius: 2, textTransform: "none", fontWeight: 600 }}
                >
                  Configure New Policy
                </Button>
              </Box>

              {loadingPolicies ? (
                <Box sx={{ display: "flex", p: 6, justifyContent: "center" }}>
                  <CircularProgress size={32} />
                </Box>
              ) : filteredPolicies.length === 0 ? (
                <Box sx={{ p: 4, textAlign: "center", color: "text.secondary" }}>
                  <Typography variant="body1" fontWeight={600}>
                    No policy rules defined for '{policyTypeFilter}' employee tier.
                  </Typography>
                </Box>
              ) : (
                <TableContainer>
                  <Table sx={{ minWidth: 700 }}>
                    <TableHead sx={{ bgcolor: "rgba(0,0,0,0.02)" }}>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 700 }}>Leave Type</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Annual Entitlement</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Carry Forward</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Notice & Rules</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Effective From</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                        <TableCell align="right" sx={{ fontWeight: 700 }}>Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {filteredPolicies.map((pol) => (
                        <TableRow key={pol.id} hover>
                          <TableCell>
                            <Typography variant="body2" fontWeight={600}>
                              {pol.leave_type_name}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              Code: {pol.leave_type_code}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" fontWeight={700} color="primary.main">
                              {pol.annual_entitlement} days / yr
                            </Typography>
                          </TableCell>
                          <TableCell>
                            {pol.allow_carry_forward ? (
                              <Chip label={`Max ${pol.max_carry_forward} days`} size="small" color="info" />
                            ) : (
                              <Typography variant="caption" color="text.secondary">No carry forward</Typography>
                            )}
                          </TableCell>
                          <TableCell>
                            <Typography variant="caption" display="block">
                              • Min Notice: {pol.min_notice_days} day(s)
                            </Typography>
                            <Typography variant="caption" display="block">
                              • Max Consecutive: {pol.max_consecutive_days} day(s)
                            </Typography>
                            <Typography variant="caption" display="block">
                              • Half-day: {pol.allow_half_day ? "Allowed" : "Not allowed"}
                            </Typography>
                            {pol.requires_document && (
                              <Chip label="Doc Required" size="small" color="warning" sx={{ height: 18, fontSize: "0.65rem", mt: 0.5 }} />
                            )}
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2">{pol.effective_from}</Typography>
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={pol.is_active ? "Active" : "Inactive"}
                              color={pol.is_active ? "success" : "default"}
                              size="small"
                            />
                          </TableCell>
                          <TableCell align="right">
                            <IconButton size="small" color="primary" onClick={() => handleOpenPolicyModal(pol)}>
                              <EditIcon fontSize="small" />
                            </IconButton>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </Box>
          )}

          {/* TAB 2: LEAVE TYPES (Super Admin) */}
          {isSuperUser && currentTab === 2 && (
            <Box sx={{ p: 3 }}>
              <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2.5 }}>
                <Typography variant="h6" fontWeight={700}>
                  System Leave Types Registry
                </Typography>
                <Button
                  variant="contained"
                  color="primary"
                  startIcon={<AddIcon />}
                  onClick={() => handleOpenTypeModal(null)}
                  sx={{ borderRadius: 2, textTransform: "none", fontWeight: 600 }}
                >
                  Create Leave Type
                </Button>
              </Box>

              {loadingPolicies ? (
                <Box sx={{ display: "flex", p: 6, justifyContent: "center" }}>
                  <CircularProgress size={32} />
                </Box>
              ) : (
                <TableContainer>
                  <Table sx={{ minWidth: 700 }}>
                    <TableHead sx={{ bgcolor: "rgba(0,0,0,0.02)" }}>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 700 }}>Name & Code</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Category</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Half Day & Dates</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Notice & Docs</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                        <TableCell align="right" sx={{ fontWeight: 700 }}>Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {allTypes.map((t) => (
                        <TableRow key={t.id} hover>
                          <TableCell>
                            <Typography variant="body2" fontWeight={600}>
                              {t.name}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {t.code}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip label={t.is_paid ? "Paid Leave" : "Unpaid Leave"} color={t.is_paid ? "success" : "default"} size="small" />
                          </TableCell>
                          <TableCell>
                            <Typography variant="caption" display="block">
                              Half Day: {t.allow_half_day ? "Yes" : "No"}
                            </Typography>
                            <Typography variant="caption" display="block">
                              Past Dates: {t.allow_past_dates ? "Allowed" : "Blocked"}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Typography variant="caption" display="block">
                              Min Notice: {t.min_notice_days} day(s)
                            </Typography>
                            <Typography variant="caption" display="block">
                              Doc Required: {t.requires_document ? "Yes" : "No"}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip label={t.is_active ? "Active" : "Inactive"} color={t.is_active ? "success" : "default"} size="small" />
                          </TableCell>
                          <TableCell align="right">
                            <IconButton size="small" color="primary" onClick={() => handleOpenTypeModal(t)}>
                              <EditIcon fontSize="small" />
                            </IconButton>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </Box>
          )}

          {/* TAB 3: EMPLOYEE BALANCES OVERVIEW */}
          {currentTab === 3 && (
            <Box sx={{ p: 3 }}>
              <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2.5, flexWrap: "wrap", gap: 2 }}>
                <Typography variant="h6" fontWeight={700}>
                  Employee Leave Balances Audit
                </Typography>
                <TextField
                  size="small"
                  placeholder="Filter by employee email..."
                  value={searchEmp}
                  onChange={(e) => setSearchEmp(e.target.value)}
                  sx={{ width: 300 }}
                />
              </Box>

              {loadingAdminBalances ? (
                <Box sx={{ display: "flex", p: 6, justifyContent: "center" }}>
                  <CircularProgress size={32} />
                </Box>
              ) : filteredBalances.length === 0 ? (
                <Box sx={{ p: 4, textAlign: "center", color: "text.secondary" }}>
                  <Typography variant="body1">No employee balances found.</Typography>
                </Box>
              ) : (
                <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  {filteredBalances.map((empObj) => (
                    <Paper key={empObj.employee_id} variant="outlined" sx={{ p: 2.5, borderRadius: 2.5 }}>
                      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 1.5 }}>
                        <Typography variant="subtitle1" fontWeight={700} color="primary.main">
                          {empObj.employee_email}
                        </Typography>
                        <Chip label={`Employment Tier: ${empObj.employment_type}`} size="small" color="secondary" />
                      </Box>

                      <TableContainer>
                        <Table size="small">
                          <TableHead sx={{ bgcolor: "rgba(0,0,0,0.02)" }}>
                            <TableRow>
                              <TableCell sx={{ fontWeight: 700 }}>Leave Type</TableCell>
                              <TableCell align="center" sx={{ fontWeight: 700 }}>Annual Entitlement</TableCell>
                              <TableCell align="center" sx={{ fontWeight: 700 }}>Carried Forward</TableCell>
                              <TableCell align="center" sx={{ fontWeight: 700 }}>Used (Approved)</TableCell>
                              <TableCell align="center" sx={{ fontWeight: 700 }}>Pending</TableCell>
                              <TableCell align="center" sx={{ fontWeight: 700 }}>Available Balance</TableCell>
                            </TableRow>
                          </TableHead>
                          <TableBody>
                            {empObj.balances.map((b) => (
                              <TableRow key={b.leave_type_id}>
                                <TableCell fontWeight={600}>{b.leave_type_name} ({b.leave_type_code})</TableCell>
                                <TableCell align="center">{b.annual_entitlement}</TableCell>
                                <TableCell align="center">{b.carried_forward}</TableCell>
                                <TableCell align="center">{b.used}</TableCell>
                                <TableCell align="center" sx={{ color: "warning.main", fontWeight: 600 }}>{b.pending}</TableCell>
                                <TableCell align="center" sx={{ color: "primary.main", fontWeight: 700 }}>{b.available}</TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </TableContainer>
                    </Paper>
                  ))}
                </Box>
              )}
            </Box>
          )}
        </Paper>

        {/* APPROVE / DENY / CANCEL ACTION DIALOG */}
        <Dialog open={actionModal.open} onClose={handleCloseAction} maxWidth="xs" fullWidth>
          <DialogTitle sx={{ fontWeight: 700 }}>
            {actionModal.type === "APPROVE" ? "Approve Leave Request" : actionModal.type === "DENY" ? "Deny Leave Request" : "Cancel Approved Leave"}
          </DialogTitle>
          <DialogContent dividers>
            {actionError && <Alert severity="error" sx={{ mb: 2 }}>{actionError}</Alert>}
            {actionModal.request && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="body2" fontWeight={600}>
                  Employee: {actionModal.request.employee_email}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Leave: {actionModal.request.leave_type_name} ({actionModal.request.duration_days} days)
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Dates: {actionModal.request.start_date} to {actionModal.request.end_date}
                </Typography>
              </Box>
            )}
            <TextField
              fullWidth
              multiline
              rows={3}
              label={actionModal.type === "DENY" ? "Reviewer Remarks (Required)" : "Reviewer Remarks (Optional)"}
              value={actionModal.remarks}
              onChange={(e) => setActionModal((prev) => ({ ...prev, remarks: e.target.value }))}
              placeholder="Add reviewer notes or reason..."
              required={actionModal.type === "DENY"}
            />
          </DialogContent>
          <DialogActions sx={{ px: 3, py: 2 }}>
            <Button onClick={handleCloseAction} color="inherit">Cancel</Button>
            <Button
              variant="contained"
              color={actionModal.type === "APPROVE" ? "success" : actionModal.type === "DENY" ? "error" : "warning"}
              onClick={handleExecuteAction}
              disabled={actionSubmitting}
            >
              {actionSubmitting ? <CircularProgress size={24} /> : "Confirm Action"}
            </Button>
          </DialogActions>
        </Dialog>

        {/* POLICY FORM MODAL */}
        <Dialog open={policyModal.open} onClose={() => setPolicyModal({ open: false, policy: null })} maxWidth="sm" fullWidth>
          <DialogTitle sx={{ fontWeight: 700 }}>
            {policyModal.policy ? "Edit Leave Policy" : "Create Leave Policy Rule"}
          </DialogTitle>
          <form onSubmit={handleSavePolicy}>
            <DialogContent dividers sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
              {policyError && <Alert severity="error">{policyError}</Alert>}

              <Grid2 container spacing={2}>
                <Grid2 size={{ xs: 6 }}>
                  <TextField
                    select
                    fullWidth
                    label="Employee Tier"
                    value={polEmployeeType}
                    onChange={(e) => setPolEmployeeType(e.target.value)}
                    required
                  >
                    <MenuItem value="PERMANENT">PERMANENT</MenuItem>
                    <MenuItem value="CONTRACT">CONTRACT</MenuItem>
                    <MenuItem value="INTERN">INTERN</MenuItem>
                  </TextField>
                </Grid2>
                <Grid2 size={{ xs: 6 }}>
                  <TextField
                    select
                    fullWidth
                    label="Leave Type"
                    value={polLeaveTypeId}
                    onChange={(e) => setPolLeaveTypeId(e.target.value)}
                    required
                  >
                    {allTypes.map((t) => (
                      <MenuItem key={t.id} value={t.id}>{t.name} ({t.code})</MenuItem>
                    ))}
                  </TextField>
                </Grid2>
              </Grid2>

              <Grid2 container spacing={2}>
                <Grid2 size={{ xs: 6 }}>
                  <TextField
                    fullWidth
                    type="number"
                    step="0.5"
                    label="Annual Entitlement (Days)"
                    value={polEntitlement}
                    onChange={(e) => setPolEntitlement(parseFloat(e.target.value))}
                    required
                  />
                </Grid2>
                <Grid2 size={{ xs: 6 }}>
                  <TextField
                    fullWidth
                    type="date"
                    label="Effective From"
                    value={polEffectiveFrom}
                    onChange={(e) => setPolEffectiveFrom(e.target.value)}
                    InputLabelProps={{ shrink: true }}
                    required
                  />
                </Grid2>
              </Grid2>

              <Grid2 container spacing={2}>
                <Grid2 size={{ xs: 6 }}>
                  <TextField
                    fullWidth
                    type="number"
                    label="Max Consecutive Days"
                    value={polMaxConsecutive}
                    onChange={(e) => setPolMaxConsecutive(parseInt(e.target.value))}
                  />
                </Grid2>
                <Grid2 size={{ xs: 6 }}>
                  <TextField
                    fullWidth
                    type="number"
                    label="Min Notice Days"
                    value={polMinNotice}
                    onChange={(e) => setPolMinNotice(parseInt(e.target.value))}
                  />
                </Grid2>
              </Grid2>

              <Box sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, p: 2 }}>
                <FormControlLabel
                  control={<Switch checked={polCarryForward} onChange={(e) => setPolCarryForward(e.target.checked)} />}
                  label="Allow Carry Forward to Next Year"
                />
                {polCarryForward && (
                  <TextField
                    fullWidth
                    size="small"
                    type="number"
                    step="0.5"
                    label="Max Carry Forward Days"
                    value={polMaxCarryForward}
                    onChange={(e) => setPolMaxCarryForward(parseFloat(e.target.value))}
                    sx={{ mt: 1 }}
                  />
                )}
              </Box>

              <Grid2 container spacing={2}>
                <Grid2 size={{ xs: 6 }}>
                  <FormControlLabel
                    control={<Switch checked={polAllowHalfDay} onChange={(e) => setPolAllowHalfDay(e.target.checked)} />}
                    label="Allow Half Day"
                  />
                </Grid2>
                <Grid2 size={{ xs: 6 }}>
                  <FormControlLabel
                    control={<Switch checked={polReqDoc} onChange={(e) => setPolReqDoc(e.target.checked)} />}
                    label="Require Document"
                  />
                </Grid2>
              </Grid2>
            </DialogContent>
            <DialogActions sx={{ px: 3, py: 2 }}>
              <Button onClick={() => setPolicyModal({ open: false, policy: null })}>Cancel</Button>
              <Button type="submit" variant="contained" color="primary" disabled={policySubmitting}>
                {policySubmitting ? <CircularProgress size={24} /> : "Save Policy"}
              </Button>
            </DialogActions>
          </form>
        </Dialog>

        {/* LEAVE TYPE FORM MODAL */}
        <Dialog open={typeModal.open} onClose={() => setTypeModal({ open: false, typeObj: null })} maxWidth="sm" fullWidth>
          <DialogTitle sx={{ fontWeight: 700 }}>
            {typeModal.typeObj ? "Edit Leave Type" : "Create Leave Type"}
          </DialogTitle>
          <form onSubmit={handleSaveType}>
            <DialogContent dividers sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
              {typeError && <Alert severity="error">{typeError}</Alert>}

              <Grid2 container spacing={2}>
                <Grid2 size={{ xs: 6 }}>
                  <TextField
                    fullWidth
                    label="Name"
                    value={typeName}
                    onChange={(e) => setTypeName(e.target.value)}
                    placeholder="e.g. Casual Leave"
                    required
                  />
                </Grid2>
                <Grid2 size={{ xs: 6 }}>
                  <TextField
                    fullWidth
                    label="Code"
                    value={typeCode}
                    onChange={(e) => setTypeCode(e.target.value)}
                    placeholder="e.g. CASUAL"
                    required
                  />
                </Grid2>
              </Grid2>

              <TextField
                fullWidth
                multiline
                rows={2}
                label="Description"
                value={typeDesc}
                onChange={(e) => setTypeDesc(e.target.value)}
              />

              <Grid2 container spacing={2}>
                <Grid2 size={{ xs: 6 }}>
                  <FormControlLabel
                    control={<Switch checked={typePaid} onChange={(e) => setTypePaid(e.target.checked)} />}
                    label="Paid Leave"
                  />
                </Grid2>
                <Grid2 size={{ xs: 6 }}>
                  <FormControlLabel
                    control={<Switch checked={typeHalfDay} onChange={(e) => setTypeHalfDay(e.target.checked)} />}
                    label="Allow Half Day"
                  />
                </Grid2>
              </Grid2>

              <Grid2 container spacing={2}>
                <Grid2 size={{ xs: 6 }}>
                  <FormControlLabel
                    control={<Switch checked={typePastDates} onChange={(e) => setTypePastDates(e.target.checked)} />}
                    label="Allow Past Dates"
                  />
                </Grid2>
                <Grid2 size={{ xs: 6 }}>
                  <FormControlLabel
                    control={<Switch checked={typeFutureDates} onChange={(e) => setTypeFutureDates(e.target.checked)} />}
                    label="Allow Future Dates"
                  />
                </Grid2>
              </Grid2>
            </DialogContent>
            <DialogActions sx={{ px: 3, py: 2 }}>
              <Button onClick={() => setTypeModal({ open: false, typeObj: null })}>Cancel</Button>
              <Button type="submit" variant="contained" color="primary" disabled={typeSubmitting}>
                {typeSubmitting ? <CircularProgress size={24} /> : "Save Leave Type"}
              </Button>
            </DialogActions>
          </form>
        </Dialog>
      </Box>
    </RequireAuth>
  );
}
