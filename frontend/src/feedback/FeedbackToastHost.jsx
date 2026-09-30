import { useEffect, useState } from "react";
import { Box, Collapse, IconButton, LinearProgress, Stack, Typography, useTheme } from "@mui/material";
import CheckCircleRoundedIcon from "@mui/icons-material/CheckCircleRounded";
import ErrorRoundedIcon from "@mui/icons-material/ErrorRounded";
import InfoRoundedIcon from "@mui/icons-material/InfoRounded";
import WarningRoundedIcon from "@mui/icons-material/WarningRounded";
import CloseRoundedIcon from "@mui/icons-material/CloseRounded";
import { getFeedbackKey } from "./feedbackState.js";

const ICONS = {
  success: CheckCircleRoundedIcon,
  error: ErrorRoundedIcon,
  warning: WarningRoundedIcon,
  info: InfoRoundedIcon,
};

const COLORS = {
  success: "success.main",
  error: "error.main",
  warning: "warning.main",
  info: "info.main",
};

function FeedbackToast({ notification, onClose }) {
  const [open, setOpen] = useState(true);
  const theme = useTheme();
  const Icon = ICONS[notification.severity];

  useEffect(() => {
    if (!notification.duration) return undefined;
    const timer = window.setTimeout(() => setOpen(false), notification.duration);
    return () => window.clearTimeout(timer);
  }, [notification.duration]);

  const close = () => setOpen(false);

  return (
    <Collapse in={open} timeout={{ enter: 260, exit: 180 }} onExited={() => onClose(notification.id)}>
      <Box
        role={notification.severity === "error" ? "alert" : "status"}
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === "Escape") close();
        }}
        sx={{
          width: "min(400px, calc(100vw - 32px))",
          overflow: "hidden",
          border: "1px solid",
          borderColor: "divider",
          borderRadius: 3,
          bgcolor: "background.paper",
          color: "text.primary",
          boxShadow: theme.palette.mode === "dark"
            ? "0 14px 38px rgba(0,0,0,.46)"
            : "0 14px 38px rgba(15,23,42,.16)",
          outline: "none",
          "&:focus-visible": { boxShadow: `0 0 0 3px ${theme.palette.primary.main}55, ${theme.palette.mode === "dark" ? "0 14px 38px rgba(0,0,0,.46)" : "0 14px 38px rgba(15,23,42,.16)"}` },
        }}
      >
        <Stack direction="row" spacing={1.25} alignItems="flex-start" sx={{ p: 1.5 }}>
          <Icon sx={{ color: COLORS[notification.severity], fontSize: 24, mt: 0.1 }} aria-hidden="true" />
          <Box sx={{ minWidth: 0, flex: 1 }}>
            <Typography variant="subtitle2" sx={{ fontWeight: 800, lineHeight: 1.25 }}>
              {notification.title}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.35, lineHeight: 1.45 }}>
              {notification.message}
            </Typography>
          </Box>
          <IconButton size="small" onClick={close} aria-label="Dismiss notification" sx={{ mt: -0.5, mr: -0.5 }}>
            <CloseRoundedIcon fontSize="small" />
          </IconButton>
        </Stack>
        {notification.duration > 0 && (
          <LinearProgress
            variant="determinate"
            value={100}
            aria-label="Notification time remaining"
            sx={{
              height: 3,
              bgcolor: "action.hover",
              "& .MuiLinearProgress-bar": {
                bgcolor: COLORS[notification.severity],
                transformOrigin: "left",
                animation: `feedbackToastProgress ${notification.duration}ms linear forwards`,
              },
              "@keyframes feedbackToastProgress": {
                from: { transform: "translateX(0) scaleX(1)" },
                to: { transform: "translateX(0) scaleX(0)" },
              },
            }}
          />
        )}
      </Box>
    </Collapse>
  );
}

export function FeedbackToastHost({ notifications, onClose }) {
  return (
    <Box
      aria-label="Notifications"
      sx={{
        position: "fixed",
        zIndex: (theme) => theme.zIndex.snackbar + 10,
        right: { xs: 16, sm: 24 },
        bottom: { xs: 16, sm: 24 },
        display: "flex",
        flexDirection: "column-reverse",
        alignItems: "flex-end",
        gap: 1,
        pointerEvents: "none",
        "& > *": { pointerEvents: "auto" },
      }}
    >
      {notifications.map((notification) => (
        <FeedbackToast key={getFeedbackKey(notification)} notification={notification} onClose={onClose} />
      ))}
    </Box>
  );
}
