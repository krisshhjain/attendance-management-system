import { Box, Paper, Typography } from "@mui/material";
import { formatDuration, formatTime } from "../../lib/date.js";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import ExitToAppIcon from "@mui/icons-material/ExitToApp";
import TimerIcon from "@mui/icons-material/Timer";
import AssignmentTurnedInIcon from "@mui/icons-material/AssignmentTurnedIn";

function StatCard({ title, value, icon, color }) {
  return (
    <Paper sx={{ p: 2.5, borderRadius: 3, border: "1px solid", borderColor: "divider", boxShadow: "none", display: "flex", alignItems: "center", gap: 2 }}>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "center", width: 48, height: 48, borderRadius: 2, bgcolor: `${color}.lighter`, color: `${color}.main` }}>
        {icon}
      </Box>
      <Box>
        <Typography variant="body2" color="text.secondary" fontWeight={500} sx={{ textTransform: "uppercase", letterSpacing: "0.5px", fontSize: "0.7rem", mb: 0.5 }}>
          {title}
        </Typography>
        <Typography variant="h6" fontWeight={700} sx={{ fontFamily: "monospace" }}>
          {value || "-"}
        </Typography>
      </Box>
    </Paper>
  );
}

export function SummaryCards({ data }) {
  if (!data) return null;

  return (
    <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)" }, gap: 2 }}>
      <StatCard
        title="Status"
        value={data.status.replace(/_/g, " ")}
        icon={<AssignmentTurnedInIcon />}
        color={data.status === "COMPLETED" ? "success" : data.status === "CHECKED_IN" ? "primary" : "warning"}
      />
      <StatCard
        title="Check In"
        value={data.check_in ? formatTime(data.check_in) : "--:--"}
        icon={<AccessTimeIcon />}
        color="info"
      />
      <StatCard
        title="Check Out"
        value={data.check_out ? formatTime(data.check_out) : "--:--"}
        icon={<ExitToAppIcon />}
        color="secondary"
      />
      <StatCard
        title="Working Duration"
        value={formatDuration(data.working_duration)}
        icon={<TimerIcon />}
        color="primary"
      />
    </Box>
  );
}
