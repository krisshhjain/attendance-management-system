import { Box, Typography } from "@mui/material";

const LABELS = {
  NOT_CHECKED_IN: "Not Checked In",
  CHECKED_IN: "Checked In",
  COMPLETED: "Completed",
  PRESENT: "Present",
  ABSENT: "Absent",
  HALF_DAY: "Half Day",
  LEAVE: "On Leave",
};

const TONES = {
  NOT_CHECKED_IN: { bgcolor: "action.hover", color: "text.secondary", borderColor: "divider" },
  CHECKED_IN: { bgcolor: "#e3f2fd", color: "#0288d1", borderColor: "#81d4fa" },
  COMPLETED: { bgcolor: "#e8f5e9", color: "#2e7d32", borderColor: "#a5d6a7" },
  PRESENT: { bgcolor: "#e8f5e9", color: "#2e7d32", borderColor: "#a5d6a7" },
  ABSENT: { bgcolor: "#ffebee", color: "#c62828", borderColor: "#ef9a9a" },
  HALF_DAY: { bgcolor: "#fff3e0", color: "#ed6c02", borderColor: "#ffcc80" },
  LEAVE: { bgcolor: "#f3e5f5", color: "#7b1fa2", borderColor: "#ce93d8" },
};

export function StatusBadge({ status }) {
  const tone = TONES[status] ?? { bgcolor: "action.hover", color: "text.secondary", borderColor: "divider" };
  const label = LABELS[status] ?? status.replaceAll("_", " ");
  
  return (
    <Box
      component="span"
      sx={{
        display: "inline-flex",
        alignItems: "center",
        gap: 1,
        borderRadius: 4,
        border: "1px solid",
        borderColor: tone.borderColor,
        px: 1.5,
        py: 0.5,
        bgcolor: tone.bgcolor,
        color: tone.color,
        typography: "caption",
        fontWeight: 600,
        textTransform: "uppercase",
        letterSpacing: 1,
      }}
    >
      <Box
        component="span"
        sx={{
          height: 6,
          width: 6,
          borderRadius: "50%",
          bgcolor: "currentColor",
        }}
      />
      {label}
    </Box>
  );
}
