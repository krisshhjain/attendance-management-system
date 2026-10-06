import React from "react";
import { Box, Button, Paper, Typography } from "@mui/material";

export default function FaceResultOverlay({ kind, title, message, onRetry, onClose }) {
  const passed = kind === "success";

  return (
    <Box
      role="status"
      aria-live="assertive"
      sx={{
        position: "absolute", inset: 0, zIndex: 5, display: "grid", placeItems: "center",
        p: 2, bgcolor: "rgba(10, 16, 28, 0.72)", backdropFilter: "blur(5px)", borderRadius: 2,
      }}
    >
      <Paper elevation={12} sx={{ width: "min(100%, 360px)", p: 3, borderRadius: 4, textAlign: "center" }}>
        <Box
          sx={{
            width: 88, height: 88, mx: "auto", mb: 2, borderRadius: "50%", display: "grid", placeItems: "center",
            color: passed ? "success.main" : "error.main",
            bgcolor: passed ? "success.lighter" : "error.lighter",
            animation: "face-result-pop 420ms cubic-bezier(.2,.8,.2,1) both",
            "@keyframes face-result-pop": { from: { transform: "scale(.55)", opacity: 0 }, to: { transform: "scale(1)", opacity: 1 } },
            "@media (prefers-reduced-motion: reduce)": { animation: "none" },
          }}
        >
          <svg width="52" height="52" viewBox="0 0 52 52" fill="none" aria-hidden="true">
            {passed ? (
              <path d="m12 27 9 9 19-21" stroke="currentColor" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
            ) : (
              <path d="m16 16 20 20m0-20L16 36" stroke="currentColor" strokeWidth="5" strokeLinecap="round" />
            )}
          </svg>
        </Box>
        <Typography variant="h5" fontWeight={750} gutterBottom>{title}</Typography>
        <Typography color="text.secondary">{message}</Typography>
        {!passed && (
          <Box sx={{ display: "flex", justifyContent: "center", gap: 1.5, mt: 3 }}>
            <Button variant="contained" onClick={onRetry}>Try again</Button>
            {onClose && <Button variant="text" onClick={onClose}>Close</Button>}
          </Box>
        )}
      </Paper>
    </Box>
  );
}
