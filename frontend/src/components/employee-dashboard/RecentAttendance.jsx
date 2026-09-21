import { Box, Paper, Typography, Button, CircularProgress } from "@mui/material";
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
      setRecords(data.slice(0, 5)); // Show only top 5
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
        <Box sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {records.map((record, index) => (
            <Box key={index} sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", p: 1.5, borderRadius: 2, bgcolor: "action.hover" }}>
              <Box>
                <Typography variant="body2" fontWeight={600}>
                  {new Date(record.date).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ fontFamily: "monospace", display: "flex", gap: 1 }}>
                  <span>IN: {record.check_in ? formatTime(record.check_in) : "--:--"}</span>
                  <span>OUT: {record.check_out ? formatTime(record.check_out) : "--:--"}</span>
                </Typography>
              </Box>
              <Box sx={{ textAlign: "right" }}>
                <StatusBadge status={record.status} />
                <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5, fontFamily: "monospace" }}>
                  {formatDuration(record.working_duration)}
                </Typography>
              </Box>
            </Box>
          ))}
        </Box>
      ) : (
        <Box sx={{ textAlign: "center", py: 4, color: "text.secondary" }}>
          <Typography variant="body2">No recent attendance found.</Typography>
        </Box>
      )}
    </Paper>
  );
}
