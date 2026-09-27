import { Box, Paper, Typography, Button, CircularProgress, Table, TableBody, TableCell, TableContainer, TableHead, TableRow } from "@mui/material";
import { Link } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import { getHistory } from "../../lib/attendance.js";
import { formatTime, formatDuration } from "../../lib/date.js";
import { StatusBadge } from "../StatusBadge.jsx";

export function RecentAttendance() {
  const [records, setRecords] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const data = await getHistory();
      setRecords([...data].sort((a, b) => new Date(b.date) - new Date(a.date)).slice(0, 5));
    } catch {
      // Silently fail on dashboard, just show empty
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <Paper sx={{ p: 3, borderRadius: 3, border: "1px solid", borderColor: "divider", boxShadow: "none", height: "100%", display: "flex", flexDirection: "column" }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
        <Typography variant="h6" sx={{ fontWeight: 600, letterSpacing: "-0.5px" }}>
          Recent Attendance
        </Typography>
        <Button component={Link} to="/attendance" variant="text" size="small" sx={{ textTransform: "none", fontWeight: 600 }}>
          View all
        </Button>
      </Box>

      {loading ? (
        <Box sx={{ display: "flex", justifyContent: "center", py: 4 }}>
          <CircularProgress size={24} />
        </Box>
      ) : records && records.length > 0 ? (
        <TableContainer>
          <Table size="small">
            <TableHead sx={{ bgcolor: "#f8fafc" }}>
              <TableRow>
                {['DATE', 'STATUS', 'CHECK IN', 'CHECK OUT', 'WORKING HOURS'].map((heading) => (
                  <TableCell key={heading} sx={{ py: 1.25, color: "#718096", fontSize: 10, fontWeight: 800, letterSpacing: "0.04em" }}>{heading}</TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {records.map((record, index) => (
                <TableRow key={record.id || `${record.date}-${index}`}>
                  <TableCell sx={{ fontSize: 11, fontWeight: 700, color: "#475569" }}>{new Date(`${record.date}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}</TableCell>
                  <TableCell><StatusBadge status={record.status} /></TableCell>
                  <TableCell sx={{ fontSize: 11, color: "#475569", fontFamily: "monospace" }}>{record.check_in ? formatTime(record.check_in) : "--:--"}</TableCell>
                  <TableCell sx={{ fontSize: 11, color: "#475569", fontFamily: "monospace" }}>{record.check_out ? formatTime(record.check_out) : "--:--"}</TableCell>
                  <TableCell sx={{ fontSize: 11, color: "#475569", fontFamily: "monospace" }}>{formatDuration(record.working_duration)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      ) : (
        <Box sx={{ textAlign: "center", py: 4, color: "text.secondary" }}>
          <Typography variant="body2">No recent attendance found.</Typography>
        </Box>
      )}
    </Paper>
  );
}
