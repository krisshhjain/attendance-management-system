import { formatDate, formatDuration, formatTime } from "../lib/date.js";
import { StatusBadge } from "./StatusBadge.jsx";
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from "@mui/material";

export function AttendanceTable({ records }) {
  return (
    <TableContainer component={Paper} elevation={0} sx={{ borderRadius: 3, border: "1px solid", borderColor: "divider" }}>
      <Table sx={{ minWidth: 640 }}>
        <TableHead sx={{ bgcolor: "background.default" }}>
          <TableRow>
            {["Date", "Status", "Check In", "Check Out", "Working Duration"].map((head) => (
              <TableCell
                key={head}
                sx={{
                  textTransform: "uppercase",
                  fontSize: "0.75rem",
                  fontWeight: 700,
                  letterSpacing: 0.5,
                  color: "text.secondary",
                  py: 2,
                }}
              >
                {head}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {records.map((record, index) => (
            <TableRow
              key={`${record.date}-${index}`}
              sx={{ "&:last-child td, &:last-child th": { border: 0 }, "&:hover": { bgcolor: "action.hover" } }}
            >
              <TableCell sx={{ fontWeight: 600 }}>
                {new Date(record.date).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", year: "numeric" })}
              </TableCell>
              <TableCell>
                <StatusBadge status={record.status} />
              </TableCell>
              <TableCell sx={{ color: "text.secondary", fontFamily: "monospace", fontSize: "0.95rem" }}>
                {record.check_in ? formatTime(record.check_in) : "--:--"}
              </TableCell>
              <TableCell sx={{ color: "text.secondary", fontFamily: "monospace", fontSize: "0.95rem" }}>
                {record.check_out ? formatTime(record.check_out) : "--:--"}
              </TableCell>
              <TableCell sx={{ fontFamily: "monospace", fontSize: "0.95rem", fontWeight: 500 }}>
                {formatDuration(record.working_duration)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
