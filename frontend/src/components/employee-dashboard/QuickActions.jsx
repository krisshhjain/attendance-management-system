import { Box, Paper, Typography, ButtonBase } from "@mui/material";
import { Link, useNavigate } from "@tanstack/react-router";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import EventNoteIcon from "@mui/icons-material/EventNote";
import SettingsIcon from "@mui/icons-material/Settings";

function ActionButton({ icon, label, path, disabled }) {
  const navigate = useNavigate();
  return (
    <ButtonBase
      onClick={() => !disabled && navigate({ to: path })}
      disabled={disabled}
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 1.5,
        p: 2,
        borderRadius: 2,
        border: "1px solid",
        borderColor: "divider",
        bgcolor: disabled ? "action.disabledBackground" : "background.paper",
        color: disabled ? "text.disabled" : "text.primary",
        transition: "all 0.2s",
        "&:hover": {
          bgcolor: disabled ? "action.disabledBackground" : "action.hover",
          borderColor: disabled ? "divider" : "primary.main",
          color: disabled ? "text.disabled" : "primary.main",
        }
      }}
    >
      <Box sx={{ color: disabled ? "inherit" : "primary.main" }}>{icon}</Box>
      <Typography variant="body2" fontWeight={500} textAlign="center" lineHeight={1.2}>
        {label}
      </Typography>
    </ButtonBase>
  );
}

export function QuickActions() {
  return (
    <Paper sx={{ p: 3, borderRadius: 3, border: "1px solid", borderColor: "divider", boxShadow: "none" }}>
      <Typography variant="h6" sx={{ fontWeight: 600, letterSpacing: "-0.5px", mb: 2 }}>
        Quick Actions
      </Typography>
      <Box sx={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 2 }}>
        <ActionButton icon={<AccessTimeIcon />} label="View Attendance" path="/attendance" />
        <ActionButton icon={<EventNoteIcon />} label="Apply for Leave" path="/leave" />
        <ActionButton icon={<SettingsIcon />} label="Settings" path="/settings" />
      </Box>
    </Paper>
  );
}
