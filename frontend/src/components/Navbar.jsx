import { Link, useNavigate } from "@tanstack/react-router";
import { useAuth } from "../lib/auth.jsx";
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  Avatar,
} from "@mui/material";

export function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const email = user?.email;
  const initials = (email ?? "U").slice(0, 2).toUpperCase();

  return (
    <AppBar position="sticky" color="inherit" elevation={1} sx={{ borderBottom: "1px solid", borderColor: "divider" }}>
      <Toolbar sx={{ mx: "auto", width: "100%", maxWidth: "lg", display: "flex", justifyContent: "space-between" }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 4 }}>
          <Box component={Link} to="/dashboard" sx={{ display: "flex", alignItems: "center", gap: 1.5, textDecoration: "none", color: "text.primary" }}>
            <Avatar sx={{ bgcolor: "primary.main", width: 32, height: 32, fontSize: "1rem", fontWeight: "bold" }}>
              A
            </Avatar>
            <Typography variant="h6" sx={{ fontWeight: 600, letterSpacing: "-0.5px" }}>
              AttendPro
            </Typography>
          </Box>
          <Box sx={{ display: { xs: "none", sm: "flex" }, gap: 1 }}>
            <Button component={Link} to="/dashboard" color="inherit">
              Dashboard
            </Button>
            <Button component={Link} to="/attendance" color="inherit">
              Attendance
            </Button>
          </Box>
        </Box>

        <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
          <Box sx={{ display: { xs: "none", sm: "flex" }, alignItems: "center", gap: 1.5 }}>
            <Avatar sx={{ width: 32, height: 32, fontSize: "0.875rem", bgcolor: "action.selected", color: "text.primary" }}>
              {initials}
            </Avatar>
            <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis" }}>
              {email}
            </Typography>
          </Box>
          <Button
            variant="outlined"
            size="small"
            onClick={() => {
              logout();
              navigate({ to: "/login" });
            }}
          >
            Logout
          </Button>
        </Box>
      </Toolbar>
      <Box sx={{ display: { xs: "flex", sm: "none" }, borderTop: "1px solid", borderColor: "divider", px: 2, py: 1, gap: 1 }}>
        <Button component={Link} to="/dashboard" color="inherit" size="small">
          Dashboard
        </Button>
        <Button component={Link} to="/attendance" color="inherit" size="small">
          Attendance
        </Button>
      </Box>
    </AppBar>
  );
}
