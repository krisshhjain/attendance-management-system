import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import { RequireAuth } from "../components/RequireAuth.jsx";
import { AttendanceTable } from "../components/AttendanceTable.jsx";
import { EmptyState, ErrorState, LoadingState } from "../components/States.jsx";
import { getHistory, getAdminAttendance, forceAdminCheckout } from "../lib/attendance.js";
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
} from "@mui/material";
import DownloadIcon from "@mui/icons-material/Download";

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

function AdminAttendanceTable({ records }) {
  return (
    <TableContainer component={Paper} elevation={0} sx={{ borderRadius: 3, border: "1px solid", borderColor: "divider" }}>
      <Table sx={{ minWidth: 700 }}>
        <TableHead sx={{ bgcolor: "background.default" }}>
          <TableRow>
            {["Employee", "Section", "Subsection", "Date", "Status", "Check In", "Check Out", "Working Hours", "Actions"].map((head) => (
              <TableCell
                key={head}
                sx={{ textTransform: "uppercase", fontSize: "0.75rem", fontWeight: 700, letterSpacing: 0.5, color: "text.secondary", py: 2 }}
                align={head === "Actions" ? "right" : "left"}
              >
                {head}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {records.map((record, index) => (
            <TableRow
              key={`${record.employee}-${record.date}-${index}`}
              sx={{ "&:last-child td, &:last-child th": { border: 0 }, "&:hover": { bgcolor: "action.hover" } }}
            >
              <TableCell sx={{ fontWeight: 600, maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {record.employee}
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
              <TableCell align="right">
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
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

// ── Excel export ──────────────────────────────────────────────────────────────

async function exportToExcel(records, date) {
  const XLSX = await import("xlsx");

  const ws_data = [
    ["Employee", "Section", "Subsection", "Date", "Check-in Time", "Check-out Time", "Working Duration", "Status"],
    ...records.map((r) => [
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
    { wch: 36 }, // Employee
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

  const handleExport = async () => {
    setExportError(null);
    try {
      await exportToExcel(filteredRecords, selectedDate);
    } catch {
      setExportError("Failed to generate Excel file. Please try again.");
    }
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

  useEffect(() => {
    const handler = (e) => handleForceCheckout(e.detail);
    window.addEventListener("force-checkout", handler);
    return () => window.removeEventListener("force-checkout", handler);
  }, [selectedDate, load]);

  const filteredRecords = filterScopedRecords(records, selectedScope) || [];
  const hasRecords = !loading && !error && filteredRecords.length > 0;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      {/* Page header + controls */}
      <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "flex-start", justifyContent: "space-between", gap: 2 }}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 700, letterSpacing: "-0.5px" }}>
            Attendance Records
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, fontWeight: 500 }}>
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
            onClick={handleExport}
            disabled={!hasRecords}
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
      {!loading && !error && (records?.length ?? 0) === 0 && (
        <Box sx={{ py: 8, textAlign: "center", color: "text.secondary" }}>
          <Typography variant="body1" fontWeight={500}>
            No attendance records found for this date.
          </Typography>
          <Typography variant="body2" sx={{ mt: 0.5 }}>
            Try selecting a different date.
          </Typography>
        </Box>
      )}
      {hasRecords && <AdminAttendanceTable records={filteredRecords} />}
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
        <Typography variant="h5" sx={{ fontWeight: 700, letterSpacing: "-0.5px" }}>
          Attendance History
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, fontWeight: 500 }}>
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
