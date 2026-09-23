import { Box, Typography } from "@mui/material";
import { useAuth } from "../../lib/auth.jsx";

export function WelcomeHeader() {
  const { user } = useAuth();
  const email = user?.email || "";
  const name = email ? email.split("@")[0] : "Employee";
  const formattedName = name.charAt(0).toUpperCase() + name.slice(1);

  // Get current time to determine greeting
  const hour = new Date().getHours();
  let greeting = "Good evening";
  if (hour < 12) greeting = "Good morning";
  else if (hour < 17) greeting = "Good afternoon";

  return (
    <Box sx={{ mb: 4 }}>
      <Typography variant="h5" sx={{ fontWeight: 700, letterSpacing: "-0.5px", color: "text.primary" }}>
        {greeting}, {formattedName}!
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, fontWeight: 500 }}>
        Here&apos;s your attendance overview for today.
      </Typography>
    </Box>
  );
}
