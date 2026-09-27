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
  Button,
} from "@mui/material";
import { Link } from "@tanstack/react-router";
import { formatTime, formatDuration } from "../../lib/date.js";
import { StatusBadge } from "../StatusBadge.jsx";

export function LatestAttendanceTable({ records }) {
  // Get the latest 10 records by check_in time, descending
  const sortedRecords = [...records]
    .filter(r => r.check_in)
    .sort((a, b) => new Date(b.check_in) - new Date(a.check_in))
    .slice(0, 10);

  return (
    <Paper
      elevation={0}
      sx={{
        borderRadius: "16px",
        border: "1px solid",
        borderColor: "divider",
        bgcolor: "white",
        boxShadow: "0px 1px 3px rgba(15,23,42,0.03)",
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <Box sx={{ p: 3, display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid #f1f5f9" }}>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 700, letterSpacing: "-0.5px", color: "#0f172a", fontSize: "16px" }}>
            Today's Latest Activity
          </Typography>
          <Typography variant="body2" sx={{ color: "#64748b", mt: 0.5, fontSize: "12px" }}>
            Most recent check-ins and check-outs
          </Typography>
        </Box>
        <Button
          component={Link}
          to="/attendance"
          variant="outlined"
          color="primary"
          size="small"
          sx={{ borderRadius: "8px", textTransform: "none", fontWeight: 600 }}
        >
          View All Attendance
        </Button>
      </Box>

      <TableContainer>
        <Table sx={{ minWidth: 700 }}>
          <TableHead sx={{ bgcolor: "#f8fafc" }}>
            <TableRow>
              {["Employee", "Department", "Status", "Check In", "Check Out", "Duration"].map((head) => (
                <TableCell
                  key={head}
                  sx={{
                    textTransform: "uppercase",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    letterSpacing: 0.5,
                    color: "#64748b",
                    py: 2,
                  }}
                >
                  {head}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {sortedRecords.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center" sx={{ py: 4, color: "text.secondary" }}>
                  No attendance records found for today.
                </TableCell>
              </TableRow>
            ) : (
              sortedRecords.map((record, index) => {
                const displayName = record.employee_name || record.employee;
                const dept = record.section || "---";

                return (
                  <TableRow
                    key={`${record.employee}-${index}`}
                    sx={{ "&:last-child td, &:last-child th": { border: 0 }, "&:hover": { bgcolor: "action.hover" } }}
                  >
                    <TableCell sx={{ fontWeight: 600, color: "#0f172a" }}>
                      {displayName}
                    </TableCell>
                    <TableCell sx={{ color: "#64748b" }}>{dept}</TableCell>
                    <TableCell>
                      <StatusBadge status={record.status} />
                    </TableCell>
                    <TableCell sx={{ color: "#64748b", fontFamily: "monospace", fontSize: "0.95rem" }}>
                      {record.check_in ? formatTime(record.check_in) : "--:--"}
                    </TableCell>
                    <TableCell sx={{ color: "#64748b", fontFamily: "monospace", fontSize: "0.95rem" }}>
                      {record.check_out ? formatTime(record.check_out) : "--:--"}
                    </TableCell>
                    <TableCell sx={{ fontFamily: "monospace", fontSize: "0.95rem", fontWeight: 500, color: "#334155" }}>
                      {formatDuration(record.working_duration)}
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
}
