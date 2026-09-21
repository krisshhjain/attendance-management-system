import { Box, Paper, Typography } from "@mui/material";

export function StatCard({ title, value, icon, subtitle, subtitleColor = "text.secondary" }) {
  return (
    <Paper
      elevation={0}
      sx={{
        p: 2.5,
        borderRadius: "16px",
        border: "1px solid",
        borderColor: "divider",
        display: "flex",
        flexDirection: "column",
        gap: 1.5,
        height: "100%",
        bgcolor: "white",
        boxShadow: "0px 2px 4px rgba(0, 0, 0, 0.02)"
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <Box sx={{ 
          width: 40, 
          height: 40, 
          borderRadius: "50%", 
          display: "flex", 
          alignItems: "center", 
          justifyContent: "center",
          bgcolor: "rgba(125, 37, 169, 0.06)",
          color: "primary.main"
        }}>
          {icon}
        </Box>
      </Box>
      <Box sx={{ mt: 1 }}>
        <Typography variant="h3" sx={{ fontWeight: 700, letterSpacing: "-1px", color: "text.primary", lineHeight: 1 }}>
          {value !== undefined && value !== null ? value : "-"}
        </Typography>
        <Typography variant="body2" sx={{ fontWeight: 500, color: "text.secondary", mt: 1 }}>
          {title}
        </Typography>
      </Box>
      {subtitle && (
        <Typography variant="caption" sx={{ color: subtitleColor, fontWeight: 500, display: "flex", alignItems: "center", gap: 0.5, mt: "auto" }}>
          {subtitle}
        </Typography>
      )}
    </Paper>
  );
}
