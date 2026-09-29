import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Snackbar,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import DownloadIcon from "@mui/icons-material/Download";
import { editAdminAttendance, forceAdminCheckout, getAdminAttendance, resetAdminAttendance } from "../../lib/attendance.js";
import { formatDuration, formatTime } from "../../lib/date.js";
import { StatusBadge } from "../StatusBadge.jsx";

function todayISO() {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function friendlyDate(value) {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString("en-US", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function localTime(value) {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

async function exportToExcel(records, date) {
  const XLSX = await import("xlsx");
  const rows = [
    ["Employee", "Email", "Section", "Subsection", "Date", "Status", "Check In", "Check Out", "Working Hours"],
    ...records.map((record) => [
      record.employee_name || record.employee,
      record.employee,
      record.section || "",
      record.subsection || "",
      record.date,
      record.status,
      record.check_in ? formatTime(record.check_in) : "",
      record.check_out ? formatTime(record.check_out) : "",
      formatDuration(record.working_duration),
    ]),
  ];
  const sheet = XLSX.utils.aoa_to_sheet(rows);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, sheet, "Attendance");
  XLSX.writeFile(workbook, `attendance_${date}.xlsx`);
}

export function AdminAttendancePage({ allowReset = false }) {
  const [selectedDate, setSelectedDate] = useState(todayISO());
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [editRecord, setEditRecord] = useState(null);
  const [resetRecord, setResetRecord] = useState(null);
  const [reason, setReason] = useState("");
  const [editFields, setEditFields] = useState({ status: "", check_in: "", check_out: "" });
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const { data: response, isLoading, isError, refetch } = useQuery({
    queryKey: ["adminAttendance", selectedDate],
    queryFn: () => getAdminAttendance(selectedDate),
  });

  const records = Array.isArray(response) ? response : response?.results || [];
  const filteredRecords = useMemo(() => records.filter((record) => {
    if (statusFilter !== "ALL" && record.status !== statusFilter) return false;
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return [record.employee_name, record.employee, record.section, record.subsection]
      .filter(Boolean)
      .some((value) => value.toLowerCase().includes(query));
  }), [records, searchQuery, statusFilter]);

  const refreshAfterMutation = async () => {
    await refetch();
    setSuccessMessage("Attendance updated successfully.");
  };

  const handleCheckout = async (record) => {
    try {
      await forceAdminCheckout({ employee: record.employee, date: selectedDate });
      await refreshAfterMutation();
    } catch (error) {
      setErrorMessage(error.message || "Could not force checkout.");
    }
  };

  const handleCheckoutAll = async () => {
    try {
      await forceAdminCheckout({ all: true, date: selectedDate });
      await refreshAfterMutation();
    } catch (error) {
      setErrorMessage(error.message || "Could not checkout all employees.");
    }
  };

  const openEdit = (record) => {
    setEditRecord(record);
    setEditFields({ status: record.status, check_in: localTime(record.check_in), check_out: localTime(record.check_out) });
    setReason("");
  };

  const handleEdit = async () => {
    try {
      await editAdminAttendance({
        employee: editRecord.employee,
        date: editRecord.date,
        reason,
        status: editFields.status,
        check_in: editFields.check_in ? new Date(`${editRecord.date}T${editFields.check_in}:00`).toISOString() : "",
        check_out: editFields.check_out ? new Date(`${editRecord.date}T${editFields.check_out}:00`).toISOString() : "",
      });
      setEditRecord(null);
      await refreshAfterMutation();
    } catch (error) {
      setErrorMessage(error.message || "Could not edit attendance.");
    }
  };

  const handleReset = async () => {
    try {
      await resetAdminAttendance({ employee: resetRecord.employee, reason, reset_type: "both" });
      setResetRecord(null);
      await refreshAfterMutation();
    } catch (error) {
      setErrorMessage(error.message || "Could not reset attendance.");
    }
  };

  if (isLoading) return <Paper sx={{ p: 5, textAlign: "center" }}><Typography color="text.secondary">Loading attendance...</Typography></Paper>;
  if (isError) return <Paper sx={{ p: 5, textAlign: "center" }}><Typography color="error" sx={{ mb: 2 }}>Could not load attendance.</Typography><Button variant="outlined" onClick={refetch}>Try again</Button></Paper>;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "flex-start", justifyContent: "space-between", gap: 2 }}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 700, color: "#0f172a" }}>Attendance Records</Typography>
          <Typography variant="body2" sx={{ color: "#64748b", mt: 0.5 }}>{friendlyDate(selectedDate)}</Typography>
        </Box>
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.5 }}>
          <TextField type="date" label="Select date" value={selectedDate} onChange={(event) => setSelectedDate(event.target.value)} size="small" InputLabelProps={{ shrink: true }} />
          <Button variant="contained" startIcon={<DownloadIcon />} onClick={() => exportToExcel(filteredRecords, selectedDate)} sx={{ textTransform: "none" }}>Download Excel</Button>
          <Button variant="outlined" color="warning" onClick={handleCheckoutAll} disabled={!filteredRecords.some((record) => record.status === "INCOMPLETE")} sx={{ textTransform: "none" }}>Checkout All</Button>
        </Box>
      </Box>

      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 1.5 }}>
        <TextField placeholder="Search employees..." size="small" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} sx={{ minWidth: 260 }} />
        <FormControl size="small" sx={{ minWidth: 170 }}><InputLabel>Status</InputLabel><Select value={statusFilter} label="Status" onChange={(event) => setStatusFilter(event.target.value)}><MenuItem value="ALL">All Statuses</MenuItem><MenuItem value="PRESENT">Present</MenuItem><MenuItem value="ABSENT">Absent</MenuItem><MenuItem value="INCOMPLETE">Incomplete</MenuItem><MenuItem value="LEAVE">Leave</MenuItem></Select></FormControl>
      </Box>

      <TableContainer component={Paper} elevation={0} sx={{ border: "1px solid #dbe3ee", borderRadius: 2, overflowX: "auto" }}>
        <Table sx={{ minWidth: 980 }}>
          <TableHead sx={{ bgcolor: "#f8fafc" }}><TableRow>{["Employee", "Section", "Subsection", "Date", "Status", "Check In", "Check Out", "Working Hours", "Actions"].map((heading) => <TableCell key={heading} sx={{ fontSize: 11, fontWeight: 800, color: "#64748b", textTransform: "uppercase" }}>{heading}</TableCell>)}</TableRow></TableHead>
          <TableBody>{filteredRecords.length === 0 ? <TableRow><TableCell colSpan={9} align="center" sx={{ py: 6 }}>No records match your filters.</TableCell></TableRow> : filteredRecords.map((record) => <TableRow key={`${record.employee}-${record.date}`} hover><TableCell><Typography sx={{ fontSize: 12, fontWeight: 700 }}>{record.employee_name || record.employee}</Typography><Typography variant="caption" color="text.secondary">{record.employee}</Typography></TableCell><TableCell sx={{ fontSize: 12 }}>{record.section || "-"}</TableCell><TableCell sx={{ fontSize: 12 }}>{record.subsection || "-"}</TableCell><TableCell sx={{ fontSize: 12 }}>{record.date}</TableCell><TableCell><StatusBadge status={record.status} /></TableCell><TableCell sx={{ fontSize: 12 }}>{formatTime(record.check_in)}</TableCell><TableCell sx={{ fontSize: 12 }}>{formatTime(record.check_out)}</TableCell><TableCell sx={{ fontSize: 12 }}>{formatDuration(record.working_duration)}</TableCell><TableCell><Box sx={{ display: "flex", gap: 0.75 }}><Button size="small" variant="outlined" color="warning" onClick={() => handleCheckout(record)} disabled={record.status !== "INCOMPLETE"} sx={{ textTransform: "none" }}>Checkout</Button>{allowReset && record.date === todayISO() && <Button size="small" variant="outlined" color="error" onClick={() => { setResetRecord(record); setReason(""); }} sx={{ textTransform: "none" }}>Reset</Button>}<Button size="small" variant="outlined" onClick={() => openEdit(record)} sx={{ textTransform: "none" }}>Edit</Button></Box></TableCell></TableRow>)}</TableBody>
        </Table>
      </TableContainer>

      <Dialog open={Boolean(editRecord)} onClose={() => setEditRecord(null)} maxWidth="sm" fullWidth><DialogTitle>Edit Attendance</DialogTitle><DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 2 }}><FormControl fullWidth size="small"><InputLabel>Status</InputLabel><Select value={editFields.status} label="Status" onChange={(event) => setEditFields({ ...editFields, status: event.target.value })}><MenuItem value="PRESENT">Present</MenuItem><MenuItem value="INCOMPLETE">Incomplete</MenuItem><MenuItem value="LEAVE">Leave</MenuItem></Select></FormControl><Box sx={{ display: "flex", gap: 2 }}><TextField fullWidth type="time" label="Check In" value={editFields.check_in} onChange={(event) => setEditFields({ ...editFields, check_in: event.target.value })} InputLabelProps={{ shrink: true }} /><TextField fullWidth type="time" label="Check Out" value={editFields.check_out} onChange={(event) => setEditFields({ ...editFields, check_out: event.target.value })} InputLabelProps={{ shrink: true }} /></Box><TextField fullWidth multiline rows={2} label="Reason for correction" value={reason} onChange={(event) => setReason(event.target.value)} /></DialogContent><DialogActions><Button onClick={() => setEditRecord(null)}>Cancel</Button><Button variant="contained" onClick={handleEdit} disabled={!reason.trim()}>Save Changes</Button></DialogActions></Dialog>
      <Dialog open={Boolean(resetRecord)} onClose={() => setResetRecord(null)} maxWidth="sm" fullWidth><DialogTitle>Reset Attendance</DialogTitle><DialogContent sx={{ pt: 2 }}><TextField fullWidth multiline rows={3} label="Reason for reset" value={reason} onChange={(event) => setReason(event.target.value)} /></DialogContent><DialogActions><Button onClick={() => setResetRecord(null)}>Cancel</Button><Button variant="contained" color="error" onClick={handleReset} disabled={!reason.trim()}>Reset Attendance</Button></DialogActions></Dialog>
      <Snackbar open={Boolean(successMessage)} autoHideDuration={4000} onClose={() => setSuccessMessage("")}><Alert severity="success" onClose={() => setSuccessMessage("")}>{successMessage}</Alert></Snackbar>
      <Snackbar open={Boolean(errorMessage)} autoHideDuration={5000} onClose={() => setErrorMessage("")}><Alert severity="error" onClose={() => setErrorMessage("")}>{errorMessage}</Alert></Snackbar>
    </Box>
  );
}

export default AdminAttendancePage;
