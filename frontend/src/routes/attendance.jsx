import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useState, useMemo } from "react";
import { RequireAuth } from "../components/RequireAuth.jsx";
import { AttendanceTable } from "../components/AttendanceTable.jsx";
import { EmptyState, ErrorState, LoadingState } from "../components/States.jsx";
import { getHistory, getAdminAttendance, forceAdminCheckout, resetAdminAttendance, editAdminAttendance } from "../lib/attendance.js";
import { apiRequest } from "../lib/api.js";
import { useQuery } from "@tanstack/react-query";
import { formatTime, formatDuration } from "../lib/date.js";
import { StatusBadge } from "../components/StatusBadge.jsx";
import { useAuth } from "../lib/auth.jsx";
import { filterScopedRecords, useOrganizationScope } from "../lib/organizationScope.jsx";
import {
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  TextField,
  Button,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  InputAdornment,
  Snackbar,
  Radio,
  RadioGroup,
  FormControlLabel,
  FormLabel,
} from "@mui/material";
import DownloadIcon from "@mui/icons-material/Download";
import SearchIcon from "@mui/icons-material/Search";
import FilterListIcon from "@mui/icons-material/FilterList";

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Returns today's date as "YYYY-MM-DD" in local time — never UTC-shifted. */
function todayISO() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Formats "YYYY-MM-DD" as a long, readable locale string. */
function friendlyDate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-US", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

// ── Route export ─────────────────────────────────────────────────────────────

export const Route = createFileRoute("/attendance")({
  head: () => ({
    meta: [
      { title: "Attendance — AttendPro" },
      { name: "description", content: "Full record of attendance check-in, check-out and working hours." },
      { property: "og:title", content: "Attendance — AttendPro" },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: () => (
    <RequireAuth>
      <AttendancePage />
    </RequireAuth>
  ),
});

// ── Admin table ───────────────────────────────────────────────────────────────
// API shape: { employee (email), date, status, check_in, check_out, working_duration }

function AdminAttendanceTable({ records, employees, date }) {
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");

  const getEmployeeName = (emp) => {
    if (typeof emp === 'string') return emp;
    if (emp?.first_name) return `${emp.first_name} ${emp.last_name || ''}`.trim();
    if (emp?.user?.first_name) return `${emp.user.first_name} ${emp.user.last_name || ''}`.trim();
    return emp?.user?.email || emp?.email || 'Unknown';
  };

  const finalRecords = useMemo(() => {
    const empList = employees || [];
    const recordMap = new Map();
    (records || []).forEach(r => recordMap.set(r.employee, r));

    // Determine weekend from the date string to avoid timezone parsing drift
    let isWeekend = false;
    if (date) {
      const [y, m, d] = date.split('-');
      const dateObj = new Date(y, m - 1, d);
      isWeekend = dateObj.getDay() === 0 || dateObj.getDay() === 6;
    }

    const merged = [];

    // Map through all active employees
    for (const emp of empList) {
      if (!emp.is_active) continue;

      const email = emp.user?.email || emp.email;
      const existing = recordMap.get(email) || recordMap.get(emp.id);
      const empName = getEmployeeName(emp);

      if (existing) {
        merged.push({ ...existing, employee_name: empName });
      } else {
        // Assume ABSENT on weekdays if no record exists, OFF on weekends
        merged.push({
          employee: email,
          employee_name: empName,
          section: emp.section,
          subsection: emp.subsection,
          date: date || todayISO(),
          status: isWeekend ? "OFF" : "ABSENT",
          check_in: null,
          check_out: null,
          working_duration: null,
        });
      }
    }

    // Add any records that belong to employees not in the active employees list (e.g. recently deactivated)
    for (const r of (records || [])) {
      if (!merged.find(m => m.employee === r.employee)) {
        merged.push(r);
      }
    }

    return merged
      .filter(r => {
        if (statusFilter !== "ALL" && r.status !== statusFilter) return false;
        if (searchQuery) {
          const lower = searchQuery.toLowerCase();
          const nameMatch = r.employee_name?.toLowerCase().includes(lower);
          const emailMatch = r.employee?.toLowerCase().includes(lower);
          const sectionMatch = r.section?.toLowerCase().includes(lower);
          if (!nameMatch && !emailMatch && !sectionMatch) return false;
        }
        return true;
      })
      .sort((a, b) => (a.employee_name || a.employee).localeCompare(b.employee_name || b.employee));
  }, [records, employees, date, searchQuery, statusFilter]);

  useEffect(() => {
    const handleExportEvent = () => {
      exportToExcel(finalRecords, date || todayISO());
    };
    window.addEventListener("export-table-excel", handleExportEvent);
    return () => window.removeEventListener("export-table-excel", handleExportEvent);
  }, [finalRecords, date]);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, justifyContent: 'space-between', alignItems: 'center' }}>
        <TextField
          placeholder="Search employees..."
          size="small"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          InputProps={{
            startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment>,
            sx: { borderRadius: 2, bgcolor: 'white' }
          }}
          sx={{ minWidth: 250 }}
        />
        <FormControl size="small" sx={{ minWidth: 200, bgcolor: 'white', borderRadius: 2 }}>
          <InputLabel>Status</InputLabel>
          <Select
            value={statusFilter}
            label="Status"
            onChange={(e) => setStatusFilter(e.target.value)}
            startAdornment={<InputAdornment position="start" sx={{ ml: 1, mr: -0.5 }}><FilterListIcon fontSize="small" /></InputAdornment>}
          >
            <MenuItem value="ALL">All Statuses</MenuItem>
            <MenuItem value="PRESENT">Present</MenuItem>
            <MenuItem value="ABSENT">Absent</MenuItem>
            <MenuItem value="INCOMPLETE">Incomplete</MenuItem>
            <MenuItem value="LEAVE">Leave</MenuItem>
            <MenuItem value="OFF">Off (Weekend)</MenuItem>
          </Select>
        </FormControl>
      </Box>

      <TableContainer
        component={Paper}
        elevation={0}
        sx={{
          borderRadius: "16px",
          border: "1px solid",
          borderColor: "divider",
          bgcolor: "white",
          boxShadow: "0px 1px 3px rgba(15,23,42,0.03)",
          overflow: "hidden",
        }}
      >
        <Table sx={{ minWidth: 700 }}>
          <TableHead sx={{ bgcolor: "#f8fafc", borderBottom: "1px solid #f1f5f9" }}>
            <TableRow>
              {["Employee", "Section", "Subsection", "Date", "Status", "Check In", "Check Out", "Working Hours", "Actions"].map((head) => (
                <TableCell
                  key={head}
                  sx={{ textTransform: "uppercase", fontSize: "0.75rem", fontWeight: 700, letterSpacing: 0.5, color: "#64748b", py: 2 }}
                  align={head === "Actions" ? "right" : "left"}
                >
                  {head}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {finalRecords.length === 0 ? (
              <TableRow>
                <TableCell colSpan={9} align="center" sx={{ py: 6, color: "text.secondary" }}>
                  <Typography variant="body1">No records match your filters.</Typography>
                </TableCell>
              </TableRow>
            ) : (
              finalRecords.map((record, index) => (
            <TableRow
              key={`${record.employee}-${record.date}-${index}`}
              sx={{ "&:last-child td, &:last-child th": { border: 0 }, "&:hover": { bgcolor: "action.hover" } }}
            >
              <TableCell sx={{ fontWeight: 600, maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                <Box sx={{ display: 'flex', flexDirection: 'column' }}>
                  <Typography variant="body2" sx={{ fontWeight: 600, color: '#0f172a' }}>
                    {record.employee_name || record.employee}
                  </Typography>
                  {record.employee_name && (
                    <Typography variant="caption" sx={{ color: 'text.secondary' }}>
                      {record.employee}
                    </Typography>
                  )}
                </Box>
              </TableCell>
              <TableCell sx={{ fontWeight: 500, color: "text.secondary" }}>
                {record.section || "—"}
              </TableCell>
              <TableCell sx={{ fontWeight: 500, color: "text.secondary" }}>
                {record.subsection || "—"}
              </TableCell>
              <TableCell sx={{ fontWeight: 500 }}>
                {new Date(record.date + "T00:00:00").toLocaleDateString("en-US", {
                  weekday: "short", month: "short", day: "numeric", year: "numeric",
                })}
              </TableCell>
              <TableCell>
                <StatusBadge status={record.status} />
              </TableCell>
              <TableCell sx={{ color: "text.secondary", fontFamily: "monospace", fontSize: "0.95rem" }}>
                {record.check_in ? formatTime(record.check_in) : "—"}
              </TableCell>
              <TableCell sx={{ color: "text.secondary", fontFamily: "monospace", fontSize: "0.95rem" }}>
                {record.check_out ? formatTime(record.check_out) : "—"}
              </TableCell>
              <TableCell sx={{ fontFamily: "monospace", fontSize: "0.95rem", fontWeight: 500 }}>
                {formatDuration(record.working_duration)}
              </TableCell>
              <TableCell align="right" sx={{ display: 'flex', justifyContent: 'flex-end', gap: 1 }}>
                {record.status === "INCOMPLETE" && (
                  <Button
                    size="small"
                    variant="outlined"
                    color="warning"
                    onClick={() => window.dispatchEvent(new CustomEvent("force-checkout", { detail: { employee: record.employee } }))}
                    sx={{ textTransform: "none", py: 0, minWidth: "auto", fontSize: "0.75rem" }}
                  >
                    Checkout
                  </Button>
                )}
                {record.date === todayISO() && (
                  <Button
                    size="small"
                    variant="outlined"
                    color="error"
                    onClick={() => window.dispatchEvent(new CustomEvent("reset-attendance", { detail: { record } }))}
                    sx={{ textTransform: "none", py: 0, minWidth: "auto", fontSize: "0.75rem" }}
                  >
                    Reset
                  </Button>
                )}
                {record.date <= todayISO() && (
                  <Button
                    size="small"
                    variant="outlined"
                    color="primary"
                    onClick={() => window.dispatchEvent(new CustomEvent("edit-attendance", { detail: { record } }))}
                    sx={{ textTransform: "none", py: 0, minWidth: "auto", fontSize: "0.75rem" }}
                  >
                    Edit
                  </Button>
                )}
              </TableCell>
            </TableRow>
          )))}
        </TableBody>
      </Table>
    </TableContainer>
    </Box>
  );
}

// ── Excel export ──────────────────────────────────────────────────────────────

async function exportToExcel(records, date) {
  const XLSX = await import("xlsx");

  const ws_data = [
    ["Employee Name", "Email", "Section", "Subsection", "Date", "Check-in Time", "Check-out Time", "Working Duration", "Status"],
    ...records.map((r) => [
      r.employee_name || r.employee,
      r.employee,
      r.section || "—",
      r.subsection || "—",
      new Date(r.date + "T00:00:00").toLocaleDateString("en-US", { year: "numeric", month: "long", day: "numeric" }),
      r.check_in ? formatTime(r.check_in) : "—",
      r.check_out ? formatTime(r.check_out) : "—",
      formatDuration(r.working_duration),
      r.status,
    ]),
  ];

  const ws = XLSX.utils.aoa_to_sheet(ws_data);

  // Freeze header row
  ws["!freeze"] = { xSplit: 0, ySplit: 1, topLeftCell: "A2", activePane: "bottomLeft" };

  // Column widths
  ws["!cols"] = [
    { wch: 25 }, // Name
    { wch: 30 }, // Email
    { wch: 10 }, // Section
    { wch: 12 }, // Subsection
    { wch: 22 }, // Date
    { wch: 14 }, // Check-in
    { wch: 14 }, // Check-out
    { wch: 18 }, // Working Duration
    { wch: 14 }, // Status
  ];

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, "Attendance");
  XLSX.writeFile(wb, `attendance_${date}.xlsx`);
}

// ── Admin attendance page ─────────────────────────────────────────────────────

function AdminAttendancePage() {
  const { selectedScope } = useOrganizationScope();
  const [selectedDate, setSelectedDate] = useState(todayISO());
  const [records, setRecords] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [exportError, setExportError] = useState(null);
  const [successMessage, setSuccessMessage] = useState("");
  const [resetModal, setResetModal] = useState({ open: false, record: null, reason: "", reset_type: "checkout_only" });
  const [editModal, setEditModal] = useState({ open: false, record: null, reason: "", status: "", check_in: "", check_out: "" });

  const { data: employees } = useQuery({
    queryKey: ["employees"],
    queryFn: () => apiRequest("/admin/employees/list/"),
  });

  const load = useCallback(async (date) => {
    setLoading(true);
    setError(false);
    setRecords(null);
    try {
      const data = await getAdminAttendance(date);
      setRecords(Array.isArray(data) ? data : data?.results ?? []);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(selectedDate);
  }, [load, selectedDate]);

  const handleDateChange = (e) => {
    const val = e.target.value;
    if (val) setSelectedDate(val);
  };



  const handleForceCheckout = async (payload) => {
    try {
      if (payload.all && (selectedScope.sectionId || selectedScope.subsectionId)) {
        await Promise.all(
          filteredRecords
            .filter((record) => record.status === "INCOMPLETE")
            .map((record) => forceAdminCheckout({ employee: record.employee, date: selectedDate })),
        );
      } else {
        await forceAdminCheckout({ ...payload, date: selectedDate });
      }
      load(selectedDate);
    } catch (err) {
      setExportError(err.message || "Failed to force checkout");
    }
  };

  const handleResetSubmit = async () => {
    try {
      await resetAdminAttendance({ 
        employee: resetModal.record.employee, 
        reason: resetModal.reason,
        reset_type: resetModal.reset_type,
      });
      setResetModal({ open: false, record: null, reason: "", reset_type: "checkout_only" });
      setSuccessMessage("Attendance successfully reset.");
      load(selectedDate);
    } catch (err) {
      setExportError(err.message || "Failed to reset attendance");
    }
  };

  const handleEditSubmit = async () => {
    try {
      let check_in_iso = "";
      if (editModal.check_in) {
        const dt = new Date(`${editModal.record.date}T${editModal.check_in}:00`);
        check_in_iso = dt.toISOString();
      }

      let check_out_iso = "";
      if (editModal.check_out) {
        const dt = new Date(`${editModal.record.date}T${editModal.check_out}:00`);
        check_out_iso = dt.toISOString();
      }

      await editAdminAttendance({
        employee: editModal.record.employee,
        date: editModal.record.date,
        reason: editModal.reason,
        status: editModal.status,
        check_in: check_in_iso,
        check_out: check_out_iso,
      });
      setEditModal({ open: false, record: null, reason: "", status: "", check_in: "", check_out: "" });
      setSuccessMessage("Attendance successfully updated.");
      load(selectedDate);
    } catch (err) {
      setExportError(err.message || "Failed to edit attendance");
    }
  };

  useEffect(() => {
    const handleForce = (e) => handleForceCheckout(e.detail);
    const handleReset = (e) => setResetModal({ open: true, record: e.detail.record, reason: "", reset_type: "checkout_only" });
    const handleEdit = (e) => {
      const record = e.detail.record;

      const getLocalTime = (isoString) => {
        if (!isoString) return "";
        const d = new Date(isoString);
        if (isNaN(d.getTime())) return "";
        return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
      };

      setEditModal({ 
        open: true, 
        record, 
        reason: "", 
        status: record.status, 
        check_in: getLocalTime(record.check_in), 
        check_out: getLocalTime(record.check_out)
      });
    };
    
    window.addEventListener("force-checkout", handleForce);
    window.addEventListener("reset-attendance", handleReset);
    window.addEventListener("edit-attendance", handleEdit);
    
    return () => {
      window.removeEventListener("force-checkout", handleForce);
      window.removeEventListener("reset-attendance", handleReset);
      window.removeEventListener("edit-attendance", handleEdit);
    };
  }, [selectedDate, load]);

  const filteredRecords = filterScopedRecords(records, selectedScope) || [];
  const hasRecords = !loading && !error && filteredRecords.length > 0;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Page header + controls */}
      <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "flex-start", justifyContent: "space-between", gap: 2, mb: 1 }}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 700, letterSpacing: "-0.5px", color: "#0f172a", fontSize: "24px" }}>
            Attendance Records
          </Typography>
          <Typography variant="body2" sx={{ color: "#64748b", mt: 0.5, fontSize: "14px" }}>
            {friendlyDate(selectedDate)}
          </Typography>
        </Box>

        <Box sx={{ display: "flex", alignItems: "center", gap: 2, flexWrap: "wrap" }}>
          <TextField
            type="date"
            value={selectedDate}
            onChange={handleDateChange}
            size="small"
            label="Select date"
            InputLabelProps={{ shrink: true }}
            inputProps={{ max: "2099-12-31" }}
            sx={{ minWidth: 170 }}
          />
          <Button
            variant="contained"
            color="primary"
            startIcon={<DownloadIcon />}
            onClick={() => window.dispatchEvent(new CustomEvent("export-table-excel"))}
            disabled={!hasRecords && (!employees || employees.length === 0)}
            sx={{ textTransform: "none", fontWeight: 600, borderRadius: 2 }}
          >
            Download Excel
          </Button>
          <Button
            variant="outlined"
            color="warning"
            onClick={() => handleForceCheckout({ all: true })}
            disabled={!hasRecords || !filteredRecords.some(r => r.status === "INCOMPLETE")}
            sx={{ textTransform: "none", fontWeight: 600, borderRadius: 2 }}
          >
            Checkout All
          </Button>
        </Box>
      </Box>

      {exportError && (
        <Alert severity="error" sx={{ borderRadius: 2 }}>{exportError}</Alert>
      )}

      {/* Table area */}
      {loading && <LoadingState message={`Loading attendance for ${selectedDate}…`} />}
      {!loading && error && <ErrorState onRetry={() => load(selectedDate)} />}
      {!loading && !error && (records?.length ?? 0) === 0 && (!employees || employees.length === 0) && (
        <Box sx={{ py: 8, textAlign: "center", color: "text.secondary" }}>
          <Typography variant="body1" fontWeight={500}>
            No attendance records found for this date.
          </Typography>
          <Typography variant="body2" sx={{ mt: 0.5 }}>
            Try selecting a different date.
          </Typography>
        </Box>
      )}
      {!loading && !error && (records?.length > 0 || employees?.length > 0) && <AdminAttendanceTable records={filteredRecords} employees={employees} date={selectedDate} />}

      {/* Reset Modal */}
      <Dialog open={resetModal.open} onClose={() => setResetModal({ ...resetModal, open: false })} maxWidth="sm" fullWidth PaperProps={{ sx: { borderRadius: "16px", boxShadow: "0 20px 25px -5px rgb(0 0 0 / 0.1)" } }}>
        <DialogTitle sx={{ fontWeight: 700, color: "#0f172a", pb: 1 }}>Reset Today's Attendance</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 3, pt: 1 }}>
          <Typography variant="body2" sx={{ color: "#64748b", mt: 1 }}>
            Select what you would like to reset for this employee today.
          </Typography>

          <FormControl>
            <FormLabel sx={{ fontWeight: 600, color: "text.primary", mb: 1 }}>Reset Options</FormLabel>
            <RadioGroup
              value={resetModal.reset_type}
              onChange={(e) => setResetModal({ ...resetModal, reset_type: e.target.value })}
            >
              <FormControlLabel 
                value="checkout_only" 
                control={<Radio />} 
                label={
                  <Box>
                    <Typography variant="body2" fontWeight={600}>Remove Checkout Only</Typography>
                    <Typography variant="caption" color="text.secondary">Keeps their original check-in time, but allows them to checkout again.</Typography>
                  </Box>
                } 
                sx={{ mb: 1.5, alignItems: "flex-start" }}
              />
              <FormControlLabel 
                value="both" 
                control={<Radio />} 
                label={
                  <Box>
                    <Typography variant="body2" fontWeight={600}>Remove Both (Full Reset)</Typography>
                    <Typography variant="caption" color="text.secondary">Clears everything. The employee will have to check in again from the start.</Typography>
                  </Box>
                }
                sx={{ alignItems: "flex-start" }}
              />
            </RadioGroup>
          </FormControl>

          <TextField
            fullWidth
            label="Reason for reset"
            variant="outlined"
            multiline
            rows={3}
            value={resetModal.reason}
            onChange={(e) => setResetModal({ ...resetModal, reason: e.target.value })}
            placeholder="e.g., Accidentally checked out, System error..."
          />
        </DialogContent>
        <DialogActions sx={{ p: 2, pt: 0 }}>
          <Button onClick={() => setResetModal({ ...resetModal, open: false })} sx={{ textTransform: "none", color: "#64748b", fontWeight: 600 }}>Cancel</Button>
          <Button onClick={handleResetSubmit} variant="contained" color="error" disabled={!resetModal.reason.trim()} sx={{ textTransform: "none", borderRadius: 2, fontWeight: 600, boxShadow: "none" }}>Reset Attendance</Button>
        </DialogActions>
      </Dialog>

      {/* Edit Modal */}
      <Dialog open={editModal.open} onClose={() => setEditModal({ ...editModal, open: false })} maxWidth="sm" fullWidth PaperProps={{ sx: { borderRadius: "16px", boxShadow: "0 20px 25px -5px rgb(0 0 0 / 0.1)" } }}>
        <DialogTitle sx={{ fontWeight: 700, color: "#0f172a", pb: 1 }}>Edit Attendance</DialogTitle>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2.5, pt: 1 }}>
          <Typography variant="body2" sx={{ color: "#64748b" }}>
            Modifying attendance records will be audited.
          </Typography>
          <FormControl fullWidth size="small">
            <InputLabel>Status</InputLabel>
            <Select
              value={editModal.status}
              label="Status"
              onChange={(e) => setEditModal({ ...editModal, status: e.target.value })}
            >
              <MenuItem value="PRESENT">Present</MenuItem>
              <MenuItem value="INCOMPLETE">Incomplete</MenuItem>
              <MenuItem value="LEAVE">Leave</MenuItem>
            </Select>
          </FormControl>
          <Box sx={{ display: "flex", gap: 2 }}>
            <TextField
              fullWidth
              type="time"
              label="Check In"
              size="small"
              InputLabelProps={{ shrink: true }}
              value={editModal.check_in}
              onChange={(e) => setEditModal({ ...editModal, check_in: e.target.value })}
            />
            <TextField
              fullWidth
              type="time"
              label="Check Out"
              size="small"
              InputLabelProps={{ shrink: true }}
              value={editModal.check_out}
              onChange={(e) => setEditModal({ ...editModal, check_out: e.target.value })}
            />
          </Box>
          <TextField
            fullWidth
            label="Reason for correction"
            variant="outlined"
            size="small"
            multiline
            rows={2}
            value={editModal.reason}
            onChange={(e) => setEditModal({ ...editModal, reason: e.target.value })}
          />
        </DialogContent>
        <DialogActions sx={{ p: 2, pt: 0 }}>
          <Button onClick={() => setEditModal({ ...editModal, open: false })} sx={{ textTransform: "none", color: "#64748b", fontWeight: 600 }}>Cancel</Button>
          <Button onClick={handleEditSubmit} variant="contained" color="primary" disabled={!editModal.reason.trim()} sx={{ textTransform: "none", borderRadius: 2, fontWeight: 600, boxShadow: "none" }}>Save Changes</Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={!!successMessage}
        autoHideDuration={4000}
        onClose={() => setSuccessMessage("")}
        anchorOrigin={{ vertical: "bottom", horizontal: "center" }}
      >
        <Alert onClose={() => setSuccessMessage("")} severity="success" sx={{ width: "100%", borderRadius: 2, fontWeight: 500 }}>
          {successMessage}
        </Alert>
      </Snackbar>
    </Box>
  );
}

// ── Employee attendance page (unchanged) ──────────────────────────────────────

function EmployeeAttendancePage() {
  const [records, setRecords] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      setRecords(await getHistory());
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Box sx={{ mb: 1 }}>
        <Typography variant="h5" sx={{ fontWeight: 700, letterSpacing: "-0.5px", color: "#0f172a", fontSize: "24px" }}>
          Attendance History
        </Typography>
        <Typography variant="body2" sx={{ color: "#64748b", mt: 0.5, fontSize: "14px" }}>
          A complete record of your daily check-in, check-out, and working hours.
        </Typography>
      </Box>
      {loading && <LoadingState message="Loading attendance..." />}
      {!loading && error && <ErrorState onRetry={load} />}
      {!loading && !error && (records?.length ?? 0) === 0 && <EmptyState />}
      {!loading && !error && records && records.length > 0 && <AttendanceTable records={records} />}
    </Box>
  );
}

// ── Root component — role router ──────────────────────────────────────────────

function AttendancePage() {
  const { user, loginType } = useAuth();
  const isAdmin = (user?.is_superuser || user?.is_staff) && (loginType === "admin" || loginType === "systemadmin");
  return isAdmin ? <AdminAttendancePage /> : <EmployeeAttendancePage />;
}
