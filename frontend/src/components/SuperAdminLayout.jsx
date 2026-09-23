import React from "react";
import { Box, AppBar, Toolbar, Typography, Avatar, IconButton, useTheme, useMediaQuery } from "@mui/material";
import { Sidebar } from "./Sidebar.jsx";
import { useAuth } from "../lib/auth.jsx";
import MenuIcon from "@mui/icons-material/Menu";
import NotificationsNoneIcon from "@mui/icons-material/NotificationsNone";

const DRAWER_WIDTH = 260;

export function SuperAdminLayout({ children, title }) {
  const { user } = useAuth();
  const email = user?.email;
  const initials = (email ?? "U").slice(0, 2).toUpperCase();

  const today = new Date().toLocaleDateString("en-US", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });

  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down("sm"));
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const handleDrawerToggle = () => setMobileOpen((prev) => !prev);

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: "#f5f6f8" }}>
      <Sidebar mobileOpen={mobileOpen} handleDrawerToggle={handleDrawerToggle} isMobile={isMobile} />
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          display: "flex",
          flexDirection: "column",
          width: isMobile ? "100%" : `calc(100% - ${DRAWER_WIDTH}px)`,
          minWidth: 0,
        }}
      >
        <AppBar
          position="sticky"
          elevation={0}
          sx={{
            bgcolor: "transparent",
            color: "text.primary",
            px: { xs: 2, sm: 4 },
            pt: 2,
            pb: 1,
          }}
        >
          <Toolbar disableGutters sx={{ minHeight: "48px !important", justifyContent: "space-between" }}>
            {/* Left: hamburger on mobile, date on desktop */}
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              {isMobile && (
                <IconButton edge="start" color="inherit" aria-label="open menu" onClick={handleDrawerToggle} sx={{ mr: 1 }}>
                  <MenuIcon />
                </IconButton>
              )}
              <Box
                sx={{
                  display: { xs: "none", sm: "flex" },
                  alignItems: "center",
                  gap: 1,
                  bgcolor: "white",
                  px: 2,
                  py: 1,
                  borderRadius: 2,
                  boxShadow: "0 1px 2px rgba(0,0,0,0.05)",
                }}
              >
                <Typography variant="body2" fontWeight={600} color="text.primary">
                  {today}
                </Typography>
              </Box>
            </Box>

            {/* Right: notification + user */}
            <Box sx={{ display: "flex", alignItems: "center", gap: { xs: 1, sm: 2 } }}>
              <IconButton size="small" sx={{ bgcolor: "white", boxShadow: "0 1px 2px rgba(0,0,0,0.05)" }}>
                <NotificationsNoneIcon fontSize="small" />
              </IconButton>

              <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                <Box sx={{ textAlign: "right", display: { xs: "none", sm: "block" } }}>
                  <Typography variant="body2" fontWeight={600}>
                    {email?.split("@")[0] || "Super Admin"}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {email}
                  </Typography>
                </Box>
                <Avatar sx={{ width: 38, height: 38, bgcolor: "primary.main", fontSize: "1rem", fontWeight: "bold" }}>
                  {initials}
                </Avatar>
              </Box>
            </Box>
          </Toolbar>
        </AppBar>
        <Box sx={{ p: { xs: 2, sm: 4 }, pt: 2, flexGrow: 1, display: "flex", flexDirection: "column" }}>
          {children}
        </Box>
      </Box>
    </Box>
  );
}
