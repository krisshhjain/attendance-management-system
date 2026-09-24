import { Box, Paper, Typography } from "@mui/material";

export function StatCard({ title, value, icon, subtitle, subtitleColor = "text.secondary", colorClass = "primary", onClick }) {
  // Map colorClass to specific background/text colors based on Figma's palette
  const colorMap = {
    primary: { bg: "#eef2ff", text: "#4f46e5" }, // indigo
    success: { bg: "#ecfdf5", text: "#059669" }, // emerald
    error: { bg: "#fff1f2", text: "#e11d48" },   // rose
    warning: { bg: "#fffbeb", text: "#d97706" }, // amber
  };

  const colors = colorMap[colorClass] || colorMap.primary;

  return (
    <Paper
      elevation={0}
      onClick={onClick}
      sx={{
        p: 2.5,
        borderRadius: "16px",
        border: "1px solid",
        borderColor: "divider",
        bgcolor: "white",
        boxShadow: "0px 1px 3px rgba(15,23,42,0.03)",
        transition: "transform 0.2s, box-shadow 0.2s",
        "&:hover": {
          transform: "translateY(-2px)",
          boxShadow: "0px 4px 6px -1px rgba(0, 0, 0, 0.1), 0px 2px 4px -1px rgba(0, 0, 0, 0.06)",
        },
        display: "flex",
        flexDirection: "column",
        height: "100%",
        cursor: onClick ? "pointer" : "default",
      }}
    >
      <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <Box
          sx={{
            width: 44,
            height: 44,
            borderRadius: "12px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            bgcolor: colors.bg,
            color: colors.text,
          }}
        >
          {icon}
        </Box>
      </Box>
      
      <Typography variant="body2" sx={{ mt: 2.5, fontSize: "13px", fontWeight: 500, color: "#64748b" }}>
        {title}
      </Typography>
      
      <Typography variant="h3" sx={{ mt: 0.5, fontSize: "24px", fontWeight: 700, letterSpacing: "-0.025em", color: "#0f172a", lineHeight: 1 }}>
        {value !== undefined && value !== null ? value : "—"}
      </Typography>
      
      {subtitle && (
        <Typography variant="caption" sx={{ mt: 1, fontSize: "12px", color: subtitleColor === "text.secondary" ? "#94a3b8" : subtitleColor, fontWeight: 500 }}>
          {subtitle}
        </Typography>
      )}
    </Paper>
  );
}
