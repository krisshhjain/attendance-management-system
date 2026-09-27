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
import CalendarMonthOutlinedIcon from "@mui/icons-material/CalendarMonthOutlined";
import EventAvailableOutlinedIcon from "@mui/icons-material/EventAvailableOutlined";
import AutorenewOutlinedIcon from "@mui/icons-material/AutorenewOutlined";
import PersonOutlineOutlinedIcon from "@mui/icons-material/PersonOutlineOutlined";
import SettingsOutlinedIcon from "@mui/icons-material/SettingsOutlined";
import ExitToAppOutlinedIcon from "@mui/icons-material/ExitToAppOutlined";
import { useAuth } from "../../lib/auth.jsx";

const DRAWER_WIDTH = 248;

export function EmployeeSidebar({ mobileOpen, handleDrawerToggle, isMobile }) {
  const { logout, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const isMobileScreen = useMediaQuery(theme.breakpoints.down("sm"));
  const open = typeof mobileOpen !== "undefined" ? mobileOpen : isMobileScreen;

  const handleLogout = () => {
    logout();
    navigate({ to: "/login" });
  };

  const displayName = user?.first_name || user?.name || user?.email?.split("@")[0] || "Employee";
  const initials = (displayName || "E").slice(0, 2).toUpperCase();

  const appAccess = user?.app_access || { dashboard: true, attendance: true, leave: true };

  const workspaceItems = [
    { text: "Dashboard", icon: <DashboardOutlinedIcon fontSize="small" />, path: "/dashboard" },
    { text: "My Team", icon: <GroupsOutlinedIcon fontSize="small" />, path: "/my-team" },
    { text: "My Attendance", icon: <CalendarMonthOutlinedIcon fontSize="small" />, path: "/attendance" },
    { text: "My Leave", icon: <EventAvailableOutlinedIcon fontSize="small" />, path: "/leave" },
    { text: "Regularization", icon: <AutorenewOutlinedIcon fontSize="small" />, path: "/regularization" },
  ].filter((item) => appAccess[item.path.split("/")[1]] !== false || ["attendance", "dashboard", "leave", "my-team"].includes(item.path.split("/")[1]));

  const personalItems = [
    { text: "My Profile", icon: <PersonOutlineOutlinedIcon fontSize="small" />, path: "/settings" },
  ];

  const systemItems = [{ text: "Settings", icon: <SettingsOutlinedIcon fontSize="small" />, path: "/settings" }];

  const renderNav = (items) => (
    <List sx={{ px: 1.5, py: 0 }}>
      {items.map((item) => {
        const isActive =
          item.path !== "/" &&
          (location.pathname === item.path || location.pathname.startsWith(item.path + "/"));
        return (
          <ListItem key={item.text} disablePadding sx={{ mb: 0.5 }}>
            <ListItemButton
              component={Link}
              to={item.path}
              onClick={() => {
                if (isMobile) handleDrawerToggle();
              }}
              sx={{
                minHeight: 44,
                borderRadius: "12px",
                py: 1,
                px: 1.5,
                position: "relative",
                transition: "all 0.18s ease",
                background: isActive
                  ? "linear-gradient(135deg, rgba(99,102,241,0.14) 0%, rgba(139,92,246,0.10) 100%)"
                  : "transparent",
                color: isActive ? "#4338ca" : "#64748b",
                "&::before": isActive
                  ? {
                      content: '""',
                      position: "absolute",
                      left: -6,
                      top: "50%",
                      transform: "translateY(-50%)",
                      width: 4,
                      height: 20,
                      borderRadius: "0 4px 4px 0",
                      background: "linear-gradient(180deg, #6366f1, #8b5cf6)",
                    }
                  : {},
                "&:hover": {
                  backgroundColor: isActive ? undefined : "rgba(99, 102, 241, 0.06)",
                  color: isActive ? "#4338ca" : "#1e293b",
                },
              }}
            >
              <ListItemIcon
                sx={{
                  minWidth: 30,
                  color: "inherit",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                {item.icon}
              </ListItemIcon>
              <ListItemText
                primary={item.text}
                primaryTypographyProps={{
                  fontWeight: isActive ? 700 : 500,
                  fontSize: "0.9rem",
                  lineHeight: 1.2,
                  color: "inherit",
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
        width: { xs: 0, sm: DRAWER_WIDTH },
        flexShrink: 0,
        [`& .MuiDrawer-paper`]: {
          width: { xs: "82vw", sm: DRAWER_WIDTH },
          maxWidth: "320px",
          boxSizing: "border-box",
          backgroundColor: "#fdfdff",
          borderRight: isMobile ? "none" : "1px solid #eef0f5",
          boxShadow: isMobile ? "0 0 24px rgba(15, 23, 42, 0.12)" : "none",
          display: "flex",
          flexDirection: "column",
          px: 0,
          overflow: "hidden",
        },
      }}
    >
      {/* Brand */}
      <Box sx={{ px: 2.5, py: 2.75, display: "flex", alignItems: "center", gap: 1.5 }}>
        <Box
          sx={{
            width: 36,
            height: 36,
            background: "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
            borderRadius: "11px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#fff",
            fontWeight: 800,
            fontSize: "1.05rem",
            boxShadow: "0 6px 16px rgba(99, 102, 241, 0.35)",
          }}
        >
          A
        </Box>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 800, color: "#0f172a", letterSpacing: "-0.5px", lineHeight: 1.1, fontSize: "1.05rem" }}>
            AttendPro
          </Typography>
          <Typography variant="caption" sx={{ color: "#94a3b8", fontWeight: 500 }}>
            Attendance Suite
          </Typography>
        </Box>
      </Box>

      {/* Nav — scrolls internally only if it truly overflows, no visible scrollbar */}
      <Box
        sx={{
          flexGrow: 1,
          overflowY: "auto",
          overflowX: "hidden",
          pt: 0.5,
          "&::-webkit-scrollbar": { width: 0, height: 0 },
          scrollbarWidth: "none",
          msOverflowStyle: "none",
        }}
      >
        <Box sx={{ px: 2.75, pb: 1, pt: 0.5 }}>
          <Typography variant="caption" sx={{ color: "#a3aebe", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.8px", fontSize: "0.68rem" }}>
            Workspace
          </Typography>
        </Box>
        {renderNav(workspaceItems)}

        <Box sx={{ px: 2.75, pb: 1, pt: 1.75 }}>
          <Typography variant="caption" sx={{ color: "#a3aebe", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.8px", fontSize: "0.68rem" }}>
            Personal
          </Typography>
        </Box>
        {renderNav(personalItems)}

        <Box sx={{ px: 2.75, pb: 1, pt: 1.75 }}>
          <Typography variant="caption" sx={{ color: "#a3aebe", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.8px", fontSize: "0.68rem" }}>
            System
          </Typography>
        </Box>
        {renderNav(systemItems)}
      </Box>

      {/* Footer / profile */}
      <Box sx={{ px: 2, pb: 2.25, pt: 1.5, borderTop: "1px solid #eef0f5" }}>
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 1.3,
            p: 1,
            borderRadius: "14px",
            background: "linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)",
            border: "1px solid #eef0f5",
          }}
        >
          <Box
            sx={{
              width: 36,
              height: 36,
              borderRadius: "50%",
              background: "linear-gradient(135deg, #6366f1 0%, #a855f7 100%)",
              color: "#fff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontWeight: 700,
              fontSize: "0.88rem",
              flexShrink: 0,
              boxShadow: "0 4px 10px rgba(139, 92, 246, 0.3)",
            }}
          >
            {initials}
          </Box>
          <Box sx={{ flexGrow: 1, minWidth: 0 }}>
            <Typography variant="body2" noWrap sx={{ fontWeight: 700, color: "#0f172a", lineHeight: 1.3, fontSize: "0.86rem" }}>
              {displayName}
            </Typography>
            <Typography variant="caption" noWrap sx={{ color: "#94a3b8", display: "block", fontSize: "0.72rem" }}>
              {user?.designation || "Employee"}
            </Typography>
          </Box>
        </Box>

        <List sx={{ px: 0, mt: 1 }}>
          <ListItem disablePadding>
            <ListItemButton
              onClick={handleLogout}
              sx={{
                borderRadius: "12px",
                py: 1,
                px: 1.5,
                color: "#64748b",
                transition: "all 0.18s ease",
                "&:hover": { color: "#dc2626", backgroundColor: "#fef2f2" },
              }}
            >
              <ListItemIcon sx={{ minWidth: 32, color: "inherit" }}>
                <ExitToAppOutlinedIcon fontSize="small" />
              </ListItemIcon>
              <ListItemText
                primary="Logout"
                primaryTypographyProps={{ fontWeight: 600, fontSize: "0.88rem" }}
              />
            </ListItemButton>
          </ListItem>
        </List>
      </Box>
    </Drawer>
  );
}