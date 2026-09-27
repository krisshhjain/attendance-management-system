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
  useTheme,
  useMediaQuery,
} from "@mui/material";
import DashboardOutlinedIcon from "@mui/icons-material/DashboardOutlined";
import GroupsOutlinedIcon from "@mui/icons-material/GroupsOutlined";
import AccessTimeOutlinedIcon from "@mui/icons-material/AccessTimeOutlined";
import EventAvailableOutlinedIcon from "@mui/icons-material/EventAvailableOutlined";
import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import ExitToAppOutlinedIcon from "@mui/icons-material/ExitToAppOutlined";
import { useAuth } from "../../lib/auth.jsx";

const DRAWER_WIDTH = 240;

export function EmployeeSidebar({ mobileOpen, handleDrawerToggle, isMobile }) {
  const { logout, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const isMobileScreen = useMediaQuery(theme.breakpoints.down('sm'));
  // Use prop state when provided, fallback to internal detection
  const open = typeof mobileOpen !== 'undefined' ? mobileOpen : isMobileScreen;


  const handleLogout = () => {
    logout();
    navigate({ to: "/login" });
  };

  const appAccess = user?.app_access || { dashboard: true, attendance: true, leave: true };
  const mainNav = [
    { text: "Dashboard", icon: <DashboardOutlinedIcon />, path: "/dashboard" },
    { text: "My Team", icon: <GroupsOutlinedIcon />, path: "/my-team" },
    { text: "Attendance", icon: <AccessTimeOutlinedIcon />, path: "/attendance" },
    { text: "Leave", icon: <EventAvailableOutlinedIcon />, path: "/leave" },
  ].filter((item) => appAccess[item.path.slice(1)] !== false);

  const bottomNav = [
    { text: "Settings", icon: <SettingsOutlinedIcon />, path: "/settings" },
  ];

  const renderNav = (items) => (
    <List sx={{ px: 2 }}>
      {items.map((item) => {
        const isActive = location.pathname.startsWith(item.path) && item.path !== "/";
        return (
          <ListItem key={item.text} disablePadding sx={{ mb: 0.5 }}>
            <ListItemButton
              component={Link}
              to={item.path}
              onClick={() => {
                if (isMobile) handleDrawerToggle();
              }}
              sx={{
                borderRadius: "10px",
                py: 1.25,
                backgroundColor: isActive ? "rgba(125, 37, 169, 0.06)" : "transparent",
                color: isActive ? "primary.main" : "text.secondary",
                "&:hover": {
                  backgroundColor: isActive ? "rgba(125, 37, 169, 0.08)" : "action.hover",
                },
              }}
            >
              <ListItemIcon
                sx={{
                  minWidth: 36,
                  color: isActive ? "primary.main" : "inherit",
                }}
              >
                {item.icon}
              </ListItemIcon>
              <ListItemText
                primary={item.text}
                primaryTypographyProps={{
                  fontWeight: isActive ? 600 : 500,
                  fontSize: "0.875rem",
                }}
              />
            </ListItemButton>
          </ListItem>
        );
      })}
    </List>
  );

  return (
    <Drawer
      variant={isMobile ? "temporary" : "permanent"}
      open={open}
      onClose={handleDrawerToggle}
      ModalProps={{ keepMounted: true }}
      sx={{
        width: DRAWER_WIDTH,
        flexShrink: 0,
        [`& .MuiDrawer-paper`]: {
          width: DRAWER_WIDTH,
          boxSizing: "border-box",
          backgroundColor: "#ffffff",
          borderRight: isMobile ? "none" : "1px solid",
          borderColor: "divider",
          display: "flex",
          flexDirection: "column",
        },
      }}
    >
      <Box sx={{ p: 3, pt: 4, display: "flex", alignItems: "center", gap: 1.5, mb: 2 }}>
        <Box
          sx={{
            width: 34,
            height: 34,
            bgcolor: "primary.main",
            borderRadius: "10px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "white",
            fontWeight: "bold",
            fontSize: "1.2rem",
          }}
        >
          A
        </Box>
        <Typography variant="h6" sx={{ fontWeight: 700, color: "text.primary", letterSpacing: "-0.5px" }}>
          AttendPro
        </Typography>
      </Box>

      <Box sx={{ flexGrow: 1 }}>
        <Box sx={{ px: 3, pb: 1 }}>
          <Typography variant="caption" sx={{ color: "text.disabled", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.5px" }}>
            Menu
          </Typography>
        </Box>
        {renderNav(mainNav)}
      </Box>

      <Box sx={{ pb: 2 }}>
        {renderNav(bottomNav)}
        <List sx={{ px: 2 }}>
          <ListItem disablePadding>
            <ListItemButton
              onClick={handleLogout}
              sx={{
                borderRadius: "10px",
                py: 1.25,
                color: "text.secondary",
                "&:hover": { color: "error.main", backgroundColor: "error.lighter" },
              }}
            >
              <ListItemIcon sx={{ minWidth: 36, color: "inherit" }}>
                <ExitToAppOutlinedIcon />
              </ListItemIcon>
              <ListItemText
                primary="Logout"
                primaryTypographyProps={{ fontWeight: 500, fontSize: "0.875rem" }}
              />
            </ListItemButton>
          </ListItem>
        </List>
      </Box>
    </Drawer>
  );
}
