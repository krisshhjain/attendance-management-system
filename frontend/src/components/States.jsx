import { CircularProgress, Box, Typography, Button } from "@mui/material";

export function LoadingState({ message = "Loading attendance..." }) {
  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 2,
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 2,
        px: 3,
        py: 3,
        bgcolor: "background.paper",
        color: "text.secondary",
      }}
    >
      <CircularProgress size={16} />
      <Typography variant="body2">{message}</Typography>
    </Box>
  );
}

export function ErrorState({ message = "Unable to load attendance.", onRetry }) {
  return (
    <Box
      sx={{
        border: "1px solid",
        borderColor: "error.light",
        borderRadius: 2,
        px: 3,
        py: 3,
        bgcolor: "error.50", // Or an rgba value if this throws an error, MUI v6 handles this. Let's use string.
        backgroundColor: "rgba(211, 47, 47, 0.05)",
      }}
    >
      <Typography variant="body2" sx={{ fontWeight: 600, color: "error.main" }}>
        {message}
      </Typography>
      <Typography variant="body2" sx={{ mt: 0.5, color: "text.secondary" }}>
        Please try again.
      </Typography>
      {onRetry && (
        <Button
          variant="outlined"
          color="inherit"
          onClick={onRetry}
          sx={{ mt: 2 }}
        >
          Retry
        </Button>
      )}
    </Box>
  );
}

export function EmptyState({ message = "No attendance records found." }) {
  return (
    <Box
      sx={{
        border: "1px dashed",
        borderColor: "divider",
        borderRadius: 2,
        px: 3,
        py: 6,
        bgcolor: "background.paper",
        textAlign: "center",
      }}
    >
      <Typography variant="body2" color="text.secondary">
        {message}
      </Typography>
    </Box>
  );
}
