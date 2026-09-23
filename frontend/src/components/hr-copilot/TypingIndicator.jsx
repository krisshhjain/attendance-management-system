import { Avatar, Box, CircularProgress, Typography } from "@mui/material";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";

export function TypingIndicator() {
  return <Box role="status" sx={{ display: "flex", alignItems: "center", gap: 1.5, py: 2 }}>
    <Avatar sx={{ width: 32, height: 32, bgcolor: "primary.main" }}><AutoAwesomeIcon fontSize="small" /></Avatar>
    <CircularProgress size={16} />
    <Typography variant="body2" color="text.secondary">HR Copilot is thinking…</Typography>
  </Box>;
}
