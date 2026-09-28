import { Box, Paper, Typography, Divider, Badge } from "@mui/material";
import { formatDuration, formatTime } from "../../lib/date.js";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import ExitToAppIcon from "@mui/icons-material/ExitToApp";
import TimerIcon from "@mui/icons-material/Timer";
import AssignmentTurnedInIcon from "@mui/icons-material/AssignmentTurnedIn";

function getStatStyles() {
  return {
    primary: { main: "#4f46e5", light: "#eef2ff" },
    success: { main: "#059669", light: "#d1fae5" },
    warning: { main: "#d97706", light: "#fef3c7" },
    info: { main: "#0284c7", light: "#e0f2fe" },
    secondary: { main: "#64748b", light: "#f1f5f9" },
  };
}

export function SummaryCards({ data }) {
  if (!data) return null;

  const getStatusColor = (status) => {
    switch (status) {
      case "COMPLETED": return "success";
      case "CHECKED_IN": return "primary";
      default: return "warning";
    }
  };

  const statusColor = getStatusColor(data.status);
  const statStyles = getStatStyles();

  return (
    <Paper sx={{ 
      borderRadius: 3, 
      border: "1px solid", 
      borderColor: "divider", 
      boxShadow: "none",
      overflow: "hidden",
      mb: 3,
    }}>
      {/* Header */}
      <Box sx={{ 
        display: "flex", 
        justifyContent: "space-between", 
        alignItems: "flex-start",
        p: 3,
        borderBottom: 1,
        borderColor: "divider",
        bgcolor: "primary.50",
      }}>
        <Box>
          <Typography variant="overline" sx={{ fontWeight: 600, color: "text.secondary", textTransform: "uppercase", letterSpacing: "0.1em" }}>
            Today's Attendance
          </Typography>
          <Typography variant="body1" sx={{ fontWeight: 600, color: "text.primary", mt: 0.5 }}>
            <Badge
              sx={{ 
                bgcolor: statusColor === "success" ? "success.light" : statusColor === "primary" ? "primary.light" : "warning.light",
                color: statusColor === "success" ? "success.main" : statusColor === "primary" ? "primary.main" : "warning.main",
                fontWeight: 600,
                fontSize: "0.75rem",
                height: 24,
                borderRadius: 1,
                mt: 1,
              }}
            >
              {data.status === "COMPLETED" ? "Checked Out" : data.status === "CHECKED_IN" ? "Present (In Progress)" : "Not Checked In"}
            </Badge>
          </Typography>
        </Box>
      </Box>

      {/* 3-column grid */}
      <Box sx={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", divideX: true, borderColor: "divider" }}>
        <Box sx={{ p: 3, textAlign: "center" }}>
          <AccessTimeIcon sx={{ fontSize: 24, color: "primary.main", mb: 1 }} />
          <Typography variant="body2" color="text.secondary" fontWeight={500} sx={{ textTransform: "uppercase", letterSpacing: "0.5px", fontSize: "0.7rem", mb: 0.5 }}>
            Check In
          </Typography>
          <Typography variant="h5" fontWeight={700} sx={{ fontFamily: "monospace", color: "text.primary" }}>
            {data.check_in ? formatTime(data.check_in) : "--:--"}
          </Typography>
        </Box>
        <Box sx={{ p: 3, textAlign: "center" }}>
          <ExitToAppIcon sx={{ fontSize: 24, color: "secondary.main", mb: 1 }} />
          <Typography variant="body2" color="text.secondary" fontWeight={500} sx={{ textTransform: "uppercase", letterSpacing: "0.5px", fontSize: "0.7rem", mb: 0.5 }}>
            Check Out
          </Typography>
          <Typography variant="h5" fontWeight={700} sx={{ fontFamily: "monospace", color: "text.primary" }}>
            {data.check_out ? formatTime(data.check_out) : "--:--"}
          </Typography>
        </Box>
        <Box sx={{ p: 3, textAlign: "center" }}>
          <TimerIcon sx={{ fontSize: 24, color: "info.main", mb: 1 }} />
          <Typography variant="body2" color="text.secondary" fontWeight={500} sx={{ textTransform: "uppercase", letterSpacing: "0.5px", fontSize: "0.7rem", mb: 0.5 }}>
            {!data.check_out && data.status === "CHECKED_IN" ? "Elapsed Time" : "Working Duration"}
          </Typography>
          <Typography variant="h5" fontWeight={700} sx={{ fontFamily: "monospace", color: "text.primary" }}>
            {formatDuration(data.working_duration)}
          </Typography>
        </Box>
      </Box>
    </Paper>
  );
}
