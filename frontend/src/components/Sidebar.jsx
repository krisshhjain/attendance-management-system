import { Link, useLocation, useNavigate } from "@tanstack/react-router";
import {
  Box,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
  Divider,
  useTheme,
  useMediaQuery,
} from "@mui/material";
import DashboardIcon from "@mui/icons-material/Dashboard";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import PeopleIcon from "@mui/icons-material/People";
import EventNoteIcon from "@mui/icons-material/EventNote";
import SettingsApplicationsIcon from "@mui/icons-material/SettingsApplications";
import SettingsIcon from "@mui/icons-material/Settings";
import LogoutIcon from "@mui/icons-material/Logout";
import { useAuth } from "../lib/auth.jsx";

const DRAWER_WIDTH = 260;

export function Sidebar({ mobileOpen, handleDrawerToggle, isMobile }) {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const isMobileScreen = useMediaQuery(theme.breakpoints.down("sm"));

  // Use prop state when provided, fallback to internal detection
  const resolvedIsMobile = typeof isMobile !== "undefined" ? isMobile : isMobileScreen;
  const open = typeof mobileOpen !== "undefined" ? mobileOpen : false;

  const handleLogout = () => {
    logout();
    navigate({ to: "/login" });
  };

  const navItems = [
    { text: "Dashboard", icon: <DashboardIcon />, path: "/dashboard" },
    { text: "Attendance", icon: <AccessTimeIcon />, path: "/attendance" },
    { text: "Employees", icon: <PeopleIcon />, path: "/employees" },
    { text: "Leave", icon: <EventNoteIcon />, path: "/leave" },
    { text: "Administration", icon: <SettingsApplicationsIcon />, path: "/administration" },
  ];

  const drawerContent = (
    <>
      <Box sx={{ p: 3, display: "flex", alignItems: "center", gap: 1.5 }}>
        <Box
          sx={{
            width: 32,
            height: 32,
            bgcolor: "primary.main",
            borderRadius: "8px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "white",
            fontWeight: "bold",
          }}
        >
          A
        </Box>
        <Typography variant="h6" sx={{ fontWeight: 700, color: "text.primary", letterSpacing: "-0.5px" }}>
          AttendPro
        </Typography>
      </Box>

      <Box sx={{ px: 2, pb: 1, mt: 2 }}>
        <Typography variant="caption" sx={{ color: "text.disabled", fontWeight: 600, ml: 1, textTransform: "uppercase", letterSpacing: "1px" }}>
          Main Menu
        </Typography>
      </Box>

      <List sx={{ px: 2, flexGrow: 1 }}>
        {navItems.map((item) => {
          const isActive = location.pathname.startsWith(item.path) && item.path !== "#";
          return (
            <ListItem key={item.text} disablePadding sx={{ mb: 0.5 }}>
              <ListItemButton
                component={item.disabled ? "div" : Link}
                to={item.disabled ? undefined : item.path}
                disabled={item.disabled}
                onClick={() => { if (resolvedIsMobile && !item.disabled) handleDrawerToggle?.(); }}
                sx={{
                  borderRadius: "8px",
                  backgroundColor: isActive ? "rgba(125, 37, 169, 0.08)" : "transparent",
                  color: isActive ? "primary.main" : "text.secondary",
                  "&:hover": {
                    backgroundColor: isActive ? "rgba(125, 37, 169, 0.12)" : "action.hover",
                  },
                }}
              >
                <ListItemIcon sx={{ minWidth: 36, color: isActive ? "primary.main" : "inherit" }}>
                  {item.icon}
                </ListItemIcon>
                <ListItemText
                  primary={item.text}
                  primaryTypographyProps={{ fontWeight: isActive ? 600 : 500, fontSize: "0.9rem" }}
                />
              </ListItemButton>
            </ListItem>
          );
        })}
      </List>

      <Divider sx={{ mx: 3, my: 1 }} />

      <List sx={{ px: 2, pb: 2 }}>
        <ListItem disablePadding sx={{ mb: 0.5 }}>
          <ListItemButton
            component={Link}
            to="/settings"
            onClick={() => { if (resolvedIsMobile) handleDrawerToggle?.(); }}
            sx={{
              borderRadius: "8px",
              color: location.pathname === "/settings" ? "primary.main" : "text.secondary",
              backgroundColor: location.pathname === "/settings" ? "rgba(125, 37, 169, 0.08)" : "transparent",
            }}
          >
            <ListItemIcon sx={{ minWidth: 36, color: "inherit" }}>
              <SettingsIcon />
            </ListItemIcon>
            <ListItemText primary="Settings" primaryTypographyProps={{ fontWeight: 500, fontSize: "0.9rem" }} />
          </ListItemButton>
        </ListItem>
        <ListItem disablePadding>
          <ListItemButton
            onClick={handleLogout}
            sx={{
              borderRadius: "8px",
              color: "text.secondary",
              "&:hover": { color: "error.main", backgroundColor: "error.lighter" },
            }}
          >
            <ListItemIcon sx={{ minWidth: 36, color: "inherit" }}>
              <LogoutIcon />
            </ListItemIcon>
            <ListItemText primary="Logout" primaryTypographyProps={{ fontWeight: 500, fontSize: "0.9rem" }} />
          </ListItemButton>
        </ListItem>
      </List>
    </>
  );

  return (
    <Drawer
      variant={resolvedIsMobile ? "temporary" : "permanent"}
      open={resolvedIsMobile ? open : true}
      onClose={handleDrawerToggle}
      ModalProps={{ keepMounted: true }}
      sx={{
        width: DRAWER_WIDTH,
        flexShrink: 0,
        [`& .MuiDrawer-paper`]: {
          width: DRAWER_WIDTH,
          boxSizing: "border-box",
          backgroundColor: "#fcfcfc",
          borderRight: resolvedIsMobile ? "none" : "1px solid",
          borderColor: "divider",
          display: "flex",
          flexDirection: "column",
        },
      }}
    >
      {drawerContent}
    </Drawer>
  );
}
