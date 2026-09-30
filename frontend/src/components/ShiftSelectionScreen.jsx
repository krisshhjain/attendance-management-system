import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Box,
  Typography,
  CircularProgress,
  Alert,
  Button,
  Paper,
  Radio,
  RadioGroup,
  FormControlLabel,
  Chip,
} from "@mui/material";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import ScheduleOutlinedIcon from "@mui/icons-material/ScheduleOutlined";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import { fetchActiveShifts, selfAssignShift } from "../lib/api.js";
import { useFeedback } from "../feedback/FeedbackProvider.jsx";

/**
 * Full-page gate shown to employees who have no shift assigned.
 * Props:
 *   onAssigned — callback invoked with the assigned shift object after a
 *                successful POST to /attendance/my-shift/assign/
 */
export function ShiftSelectionScreen({ onAssigned }) {
  const [selectedId, setSelectedId] = useState(null);
  const { success, notifyError } = useFeedback();

  const queryClient = useQueryClient();

  // Fetch the list of active shifts
  const {
    data,
    isLoading: shiftsLoading,
    isError: shiftsError,
    refetch,
  } = useQuery({
    queryKey: ["activeShifts"],
    queryFn: fetchActiveShifts,
    retry: 2,
  });

  const shifts = data?.shifts ?? [];
  const employmentType = data?.employment_type ?? null;
  const requiresConfiguration = data?.requires_configuration ?? false;
  const requiresSelection = data?.requires_selection ?? false;

  // Mutation: POST /attendance/my-shift/assign/
  const { mutate: assignShift, isPending: assigning } = useMutation({
    mutationFn: () => selfAssignShift(selectedId),
    onSuccess: (result) => {
      // Invalidate my-shift cache so RequireAuth re-checks correctly on future
      // page reloads
      queryClient.invalidateQueries({ queryKey: ["myShift"] });
      success("Shift assigned successfully.");
      onAssigned(result.shift);
    },
    onError: (err) => {
      notifyError(err, { title: "Shift assignment failed", fallback: "Failed to assign shift. Please try again." });
    },
  });

  const handleConfirm = () => {
    assignShift();
  };

  // ── Loading state ────────────────────────────────────────────────────────
  if (shiftsLoading) {
    return (
      <FullPageCenter>
        <CircularProgress size={40} />
        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          Loading available shifts…
        </Typography>
      </FullPageCenter>
    );
  }

  // ── Fetch error ──────────────────────────────────────────────────────────
  if (shiftsError) {
    return (
      <FullPageCenter>
        <Alert
          severity="error"
          action={
            <Button size="small" onClick={() => refetch()}>
              Retry
            </Button>
          }
          sx={{ maxWidth: 420 }}
        >
          Could not load shifts. Please check your connection and try again.
        </Alert>
      </FullPageCenter>
    );
  }

  // ── No shifts available / requires configuration ──────────────────────────
  if (requiresConfiguration || shifts.length === 0) {
    return (
      <FullPageCenter>
        <Alert severity="warning" sx={{ maxWidth: 480 }}>
          <Typography variant="body2" fontWeight={600} gutterBottom>
            Shift Configuration Required
          </Typography>
          <Typography variant="body2">
            {employmentType 
              ? `No shifts have been configured for ${employmentType} employees yet. Please contact your administrator to configure shifts for your employment type.`
              : "No active shifts are available yet. Please contact your administrator."}
          </Typography>
        </Alert>
      </FullPageCenter>
    );
  }

  // ── Exactly one shift available (auto-assigned by backend) ───────────────
  if (shifts.length === 1 && !requiresSelection) {
    // The backend automatically assigns the single shift as the effective shift
    // No selection needed - just inform the user and proceed
    const autoShift = shifts[0];
    return (
      <Box
        sx={{
          minHeight: "100vh",
          bgcolor: "#f8fafc",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          px: 2,
          py: 6,
        }}
      >
        <Box sx={{ width: "100%", maxWidth: 520, textAlign: "center" }}>
          <Box
            sx={{
              width: 56,
              height: 56,
              borderRadius: "16px",
              bgcolor: "#eef2ff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              mx: "auto",
              mb: 2.5,
            }}
          >
            <CheckCircleOutlineIcon sx={{ fontSize: 28, color: "#10b981" }} />
          </Box>
          <Typography
            variant="h5"
            sx={{ fontWeight: 700, color: "#0f172a", letterSpacing: "-0.5px", mb: 1 }}
          >
            Shift Automatically Assigned
          </Typography>
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ lineHeight: 1.6, mb: 3 }}
          >
            Your work shift has been automatically configured based on your employment type.
          </Typography>

          <Paper
            elevation={0}
            sx={{
              border: "1.5px solid #10b981",
              borderRadius: "14px",
              bgcolor: "#f0fdf4",
              px: 2.5,
              py: 2,
              mb: 3,
            }}
          >
            <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
              <Box
                sx={{
                  width: 40,
                  height: 40,
                  borderRadius: "10px",
                  bgcolor: "#10b981",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <AccessTimeIcon sx={{ fontSize: 20, color: "#ffffff" }} />
              </Box>
              <Box sx={{ flexGrow: 1, textAlign: "left" }}>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
                  <Typography variant="body1" sx={{ fontWeight: 600, color: "#065f46" }}>
                    {autoShift.name}
                  </Typography>
                  <Chip
                    label={autoShift.code}
                    size="small"
                    sx={{
                      fontSize: "0.6875rem",
                      fontWeight: 700,
                      height: 20,
                      bgcolor: "#d1fae5",
                      color: "#065f46",
                    }}
                  />
                </Box>
                <Typography variant="body2" sx={{ color: "#047857", mt: 0.25, fontWeight: 500 }}>
                  {autoShift.start_time} — {autoShift.end_time}
                </Typography>
              </Box>
            </Box>
          </Paper>

          <Button
            variant="contained"
            size="large"
            fullWidth
            onClick={() => onAssigned(autoShift)}
            sx={{
              py: 1.5,
              borderRadius: "12px",
              fontWeight: 700,
              fontSize: "0.9375rem",
              background: "#10b981",
              "&:hover": { background: "#059669" },
            }}
          >
            Continue to Dashboard
          </Button>
        </Box>
      </Box>
    );
  }

  // ── Main selection UI ────────────────────────────────────────────────────
  return (
    <Box
      sx={{
        minHeight: "100vh",
        bgcolor: "#f8fafc",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        px: 2,
        py: 6,
      }}
    >
      <Box sx={{ width: "100%", maxWidth: 520 }}>
        {/* Header */}
        <Box sx={{ textAlign: "center", mb: 5 }}>
          <Box
            sx={{
              width: 56,
              height: 56,
              borderRadius: "16px",
              bgcolor: "#eef2ff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              mx: "auto",
              mb: 2.5,
            }}
          >
            <ScheduleOutlinedIcon sx={{ fontSize: 28, color: "#4f46e5" }} />
          </Box>
          <Typography
            variant="h5"
            sx={{ fontWeight: 700, color: "#0f172a", letterSpacing: "-0.5px" }}
          >
            Select Your Work Shift
          </Typography>
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ mt: 1, lineHeight: 1.6 }}
          >
            {employmentType && `Multiple shifts are configured for ${employmentType} employees. `}
            Choose the shift that matches your schedule. This is a one-time
            selection — contact your manager if you need to change it later.
          </Typography>
        </Box>

        {/* Shift options */}
        <RadioGroup
          value={selectedId ? String(selectedId) : ""}
          onChange={(e) => {
            setSelectedId(Number(e.target.value));
          }}
          sx={{ display: "flex", flexDirection: "column", gap: 1.5, mb: 2 }}
        >
          {shifts.map((shift) => {
            const isSelected = selectedId === shift.id;
            return (
              <Paper
                key={shift.id}
                elevation={0}
                onClick={() => {
                  setSelectedId(shift.id);
                }}
                sx={{
                  border: "1.5px solid",
                  borderColor: isSelected ? "#4f46e5" : "#e2e8f0",
                  borderRadius: "14px",
                  bgcolor: isSelected ? "#eef2ff" : "#ffffff",
                  cursor: "pointer",
                  transition: "border-color 0.15s, background 0.15s, box-shadow 0.15s",
                  boxShadow: isSelected
                    ? "0 0 0 3px rgba(79,70,229,0.12)"
                    : "none",
                  "&:hover": {
                    borderColor: isSelected ? "#4f46e5" : "#a5b4fc",
                    bgcolor: isSelected ? "#eef2ff" : "#f5f3ff",
                  },
                  px: 2.5,
                  py: 2,
                  display: "flex",
                  alignItems: "center",
                  gap: 1.5,
                }}
              >
                <FormControlLabel
                  value={String(shift.id)}
                  control={
                    <Radio
                      sx={{
                        color: "#cbd5e1",
                        "&.Mui-checked": { color: "#4f46e5" },
                        p: 0,
                      }}
                    />
                  }
                  label=""
                  sx={{ m: 0, mr: 0.5 }}
                  onClick={(e) => e.stopPropagation()}
                />

                {/* Shift icon */}
                <Box
                  sx={{
                    width: 40,
                    height: 40,
                    borderRadius: "10px",
                    bgcolor: isSelected ? "#4f46e5" : "#f1f5f9",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                    transition: "background 0.15s",
                  }}
                >
                  <AccessTimeIcon
                    sx={{
                      fontSize: 20,
                      color: isSelected ? "#ffffff" : "#64748b",
                    }}
                  />
                </Box>

                {/* Shift details */}
                <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      gap: 1,
                      flexWrap: "wrap",
                    }}
                  >
                    <Typography
                      variant="body1"
                      sx={{
                        fontWeight: 600,
                        color: isSelected ? "#3730a3" : "#0f172a",
                        lineHeight: 1.3,
                      }}
                    >
                      {shift.name}
                    </Typography>
                    <Chip
                      label={shift.code}
                      size="small"
                      sx={{
                        fontSize: "0.6875rem",
                        fontWeight: 700,
                        height: 20,
                        bgcolor: isSelected ? "#c7d2fe" : "#f1f5f9",
                        color: isSelected ? "#3730a3" : "#64748b",
                        border: "none",
                      }}
                    />
                  </Box>
                  <Typography
                    variant="body2"
                    sx={{
                      color: isSelected ? "#4338ca" : "#64748b",
                      mt: 0.25,
                      fontWeight: 500,
                    }}
                  >
                    {shift.start_time} — {shift.end_time}
                  </Typography>
                </Box>

                {isSelected && (
                  <CheckCircleOutlineIcon
                    sx={{ fontSize: 20, color: "#4f46e5", flexShrink: 0 }}
                  />
                )}
              </Paper>
            );
          })}
        </RadioGroup>

        {/* Inline error from assignment attempt */}
        {/* Confirm button */}
        <Button
          variant="contained"
          size="large"
          fullWidth
          disabled={!selectedId || assigning}
          onClick={handleConfirm}
          sx={{
            py: 1.5,
            borderRadius: "12px",
            fontWeight: 700,
            fontSize: "0.9375rem",
            background: "#4f46e5",
            "&:hover": { background: "#4338ca" },
            "&.Mui-disabled": { background: "#e2e8f0", color: "#94a3b8" },
            mt: 0.5,
          }}
        >
          {assigning ? (
            <CircularProgress size={22} sx={{ color: "inherit" }} />
          ) : (
            "Confirm Shift Selection"
          )}
        </Button>

        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: "block", textAlign: "center", mt: 2, lineHeight: 1.5 }}
        >
          You can only select a shift once. To change it later, please contact
          your administrator.
        </Typography>
      </Box>
    </Box>
  );
}

/** Utility: vertically and horizontally centres its children in the viewport. */
function FullPageCenter({ children }) {
  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        bgcolor: "#f8fafc",
        gap: 2,
        px: 2,
      }}
    >
      {children}
    </Box>
  );
}
