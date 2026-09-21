import { createFileRoute } from "@tanstack/react-router";
import { RequireAuth } from "../components/RequireAuth.jsx";
import { Box, Typography, Paper, Grid2, Button, Divider } from "@mui/material";
import EventBusyIcon from "@mui/icons-material/EventBusy";
import BeachAccessIcon from "@mui/icons-material/BeachAccess";
import LocalHospitalIcon from "@mui/icons-material/LocalHospital";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import AddIcon from "@mui/icons-material/Add";

export const Route = createFileRoute("/leave")({
  component: Leave,
});

function LeaveBalanceCard({ title, icon, color }) {
  return (
    <Paper sx={{ p: 2.5, borderRadius: 3, border: "1px solid", borderColor: "divider", boxShadow: "none", display: "flex", alignItems: "center", gap: 2 }}>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "center", width: 48, height: 48, borderRadius: 2, bgcolor: `${color}.lighter`, color: `${color}.main` }}>
        {icon}
      </Box>
      <Box>
        <Typography variant="body2" color="text.secondary" fontWeight={500} sx={{ textTransform: "uppercase", letterSpacing: "0.5px", fontSize: "0.7rem", mb: 0.5 }}>
          {title}
        </Typography>
        <Typography variant="h6" fontWeight={700} sx={{ color: "text.disabled" }}>
          --
        </Typography>
      </Box>
    </Paper>
  );
}

function Leave() {
  return (
    <RequireAuth>
      <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
        <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <Box>
            <Typography variant="h5" sx={{ fontWeight: 700, letterSpacing: "-0.5px" }}>
              Leave Management
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, fontWeight: 500 }}>
              View your balances and apply for time off.
            </Typography>
          </Box>
          <Button variant="contained" color="primary" startIcon={<AddIcon />} sx={{ borderRadius: 2, textTransform: "none", fontWeight: 600 }}>
            Apply for Leave
          </Button>
        </Box>

        <Box sx={{ display: "flex", alignItems: "center", p: 2, borderRadius: 2, bgcolor: "info.lighter", color: "info.dark", border: "1px solid", borderColor: "info.light" }}>
          <Typography variant="body2" fontWeight={600}>
            Notice: The Leave Management module is currently awaiting setup. Balances and requests will appear here once enabled by your administrator.
          </Typography>
        </Box>

        <Typography variant="h6" sx={{ fontWeight: 600, mt: 1 }}>Balances</Typography>
        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", md: "repeat(4, 1fr)" }, gap: 2 }}>
          <LeaveBalanceCard title="Annual Leave" icon={<BeachAccessIcon />} color="primary" />
          <LeaveBalanceCard title="Sick Leave" icon={<LocalHospitalIcon />} color="error" />
          <LeaveBalanceCard title="Unpaid Leave" icon={<EventBusyIcon />} color="warning" />
          <LeaveBalanceCard title="Comp Time" icon={<AccessTimeIcon />} color="success" />
        </Box>

        <Paper sx={{ mt: 2, borderRadius: 3, border: "1px solid", borderColor: "divider", boxShadow: "none" }}>
          <Box sx={{ px: 3, py: 2.5, borderBottom: "1px solid", borderColor: "divider" }}>
            <Typography variant="h6" sx={{ fontWeight: 600, letterSpacing: "-0.5px" }}>
              Recent Requests
            </Typography>
          </Box>
          <Box sx={{ p: 6, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", color: "text.secondary", gap: 1 }}>
            <EventBusyIcon sx={{ fontSize: 48, color: "action.disabled" }} />
            <Typography variant="body1" fontWeight={500} color="text.primary">
              No leave requests found
            </Typography>
            <Typography variant="body2">
              When you apply for leave, your requests will appear here.
            </Typography>
          </Box>
        </Paper>
      </Box>
    </RequireAuth>
  );
}
