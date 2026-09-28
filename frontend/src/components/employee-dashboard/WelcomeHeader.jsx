import { Box, Typography, Avatar } from "@mui/material";
import { useAuth } from "../../lib/auth.jsx";

export function WelcomeHeader() {
  const { user } = useAuth();
  const email = user?.email || "";
  const name = user?.name || email.split("@")[0] || "Employee";
  const formattedName = name.charAt(0).toUpperCase() + name.slice(1);
  const initials = name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2);

  // Get current time to determine greeting
  const hour = new Date().getHours();
  let greeting = "Good evening";
  if (hour < 12) greeting = "Good morning";
  else if (hour < 17) greeting = "Good afternoon";

  return (
    <Box sx={{ mb: 3, display: "flex", alignItems: "flex-start", gap: 3 }}>
      <Avatar
        sx={{
          width: 56,
          height: 56,
          fontSize: "1.5rem",
          fontWeight: 700,
          bgcolor: "primary.main",
          color: "primary.contrastText",
          flexShrink: 0,
        }}
      >
        {initials}
      </Avatar>
      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Typography variant="h5" sx={{ fontWeight: 700, letterSpacing: "-0.5px", color: "text.primary", mb: 0.5 }}>
          {greeting}, {formattedName}!
        </Typography>
        <Typography variant="body1" color="text.secondary" sx={{ fontWeight: 500 }}>
          Here&apos;s your attendance overview for today.
        </Typography>
      </Box>
    </Box>
  );
}
