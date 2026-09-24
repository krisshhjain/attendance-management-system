import { useState } from "react";
import { Box, AppBar, Toolbar, Typography, Avatar, IconButton, useTheme, useMediaQuery } from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import { EmployeeSidebar } from "./EmployeeSidebar.jsx";
import { useAuth } from "../../lib/auth.jsx";

const DRAWER_WIDTH = 240;

export function EmployeeLayout({ children }) {
  const { user } = useAuth();
  const email = user?.email;
  const initials = (email ?? "U").slice(0, 2).toUpperCase();

  const today = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    day: "numeric",
    month: "short",
    year: "numeric",
  });

  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [mobileOpen, setMobileOpen] = useState(false);
  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", bgcolor: "#f8f9fa" }}>
      <EmployeeSidebar mobileOpen={mobileOpen} handleDrawerToggle={handleDrawerToggle} isMobile={isMobile} />
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          display: "flex",
          flexDirection: "column",
          width: isMobile ? '100%' : `calc(100% - ${DRAWER_WIDTH}px)`,
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
          <Toolbar disableGutters sx={{ minHeight: "56px !important", justifyContent: "space-between" }}>
            {isMobile && (
              <IconButton edge="start" color="inherit" aria-label="menu" onClick={handleDrawerToggle} sx={{ mr: 2 }}>
                <MenuIcon />
              </IconButton>
            )}
            <Box sx={{ display: "flex", alignItems: "center", gap: 3 }}>
              {/* Contextual Date */}
              <Box sx={{ display: { xs: "none", sm: "flex" }, alignItems: "center" }}>
                <Typography variant="body2" fontWeight={500} color="text.secondary">
                  {today}
                </Typography>
              </Box>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, pl: 3, borderLeft: "1px solid", borderColor: "divider" }}>
                <Box sx={{ textAlign: "right" }}>
                  <Typography variant="body2" fontWeight={600} color="text.primary">
                    {email?.split("@")[0] || "Employee"}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: -0.5 }}>
                    Employee
                  </Typography>
                </Box>
                <Avatar sx={{ width: 36, height: 36, bgcolor: "primary.main", fontSize: "0.9rem", fontWeight: "bold" }}>
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
