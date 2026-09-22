import { useCallback, useEffect, useRef, useState } from "react";
import { checkIn, checkOut, getToday } from "../../lib/attendance.js";
import { ApiError } from "../../lib/api.js";
import { formatDuration, formatTime } from "../../lib/date.js";
import { StatusBadge } from "../StatusBadge.jsx";
import { ErrorState, LoadingState } from "../States.jsx";
import { Box, Button, Typography, Paper, Grid2, CircularProgress } from "@mui/material";

export function TodayAttendanceWidget({ data, loading, loadError, reloadData }) {
  const [actionError, setActionError] = useState(null);
  const [pending, setPending] = useState(false);
  const [secondsRemaining, setSecondsRemaining] = useState(0);
  const inFlight = useRef(false);

  const status = data?.status;

  useEffect(() => {
    if (status !== "CHECKED_IN" || !data?.check_in) {
      setSecondsRemaining(0);
      return;
    }

    const updateTimer = () => {
      const checkInTime = new Date(data.check_in).getTime();
      const now = Date.now();
      const elapsed = Math.floor((now - checkInTime) / 1000);
      const remaining = Math.max(0, 300 - elapsed);
      setSecondsRemaining(remaining);
    };

    updateTimer();
    const interval = setInterval(updateTimer, 1000);
    return () => clearInterval(interval);
  }, [status, data?.check_in]);

  const runAction = useCallback(
    async (action) => {
      if (inFlight.current) return;
      inFlight.current = true;
      setPending(true);
      setActionError(null);
      try {
        if (action === "in") await checkIn();
        else await checkOut();
        await reloadData();
      } catch (error) {
        setActionError(
          error instanceof ApiError ? error.message : "Something went wrong. Please try again.",
        );
      } finally {
        inFlight.current = false;
        setPending(false);
      }
    },
    [reloadData],
  );

  if (loading) return <Paper sx={{ p: 4, display: "flex", justifyContent: "center", borderRadius: 3, border: "1px solid", borderColor: "divider", boxShadow: "none" }}><CircularProgress /></Paper>;
  if (loadError || !data) return <ErrorState onRetry={reloadData} />;

  return (
    <Paper sx={{ p: 3, borderRadius: 3, border: "1px solid", borderColor: "divider", boxShadow: "none", height: "100%", display: "flex", flexDirection: "column" }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: 3 }}>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 600, letterSpacing: "-0.5px" }}>
            Attendance
          </Typography>
        </Box>
        <StatusBadge status={status} />
      </Box>

      {actionError && (
        <Box
          sx={{
            mb: 2, p: 1.5, borderRadius: 2, border: "1px solid", borderColor: "error.light",
            bgcolor: "rgba(211, 47, 47, 0.05)", color: "error.main", typography: "body2",
          }}
        >
          {actionError}
        </Box>
      )}

      <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: "auto" }}>
        {status === "NOT_CHECKED_IN" && (
          <Button
            variant="contained"
            color="primary"
            disabled={pending}
            onClick={() => runAction("in")}
            fullWidth
            sx={{ py: 1.5, fontWeight: 600, borderRadius: 2, textTransform: "none", fontSize: "1rem" }}
          >
            {pending ? "Checking in..." : "Check In Now"}
          </Button>
        )}

        {status === "CHECKED_IN" && (
          <Box sx={{ display: "flex", flexDirection: "column", gap: 1 }}>
            <Button
              variant="contained"
              color={secondsRemaining > 0 ? "inherit" : "primary"}
              disabled={pending || secondsRemaining > 0}
              onClick={() => runAction("out")}
              fullWidth
              sx={{
                py: 1.5,
                fontWeight: 600,
                borderRadius: 2,
                textTransform: "none",
                fontSize: "1rem",
                ...(secondsRemaining > 0 && {
                  bgcolor: "action.disabledBackground",
                  color: "text.secondary",
                })
              }}
            >
              {pending
                ? "Checking out..."
                : secondsRemaining > 0
                ? `Check Out (${Math.floor(secondsRemaining / 60)}:${(secondsRemaining % 60).toString().padStart(2, "0")} resting period)`
                : "Check Out"}
            </Button>
            {secondsRemaining > 0 && (
              <Typography variant="caption" color="text.secondary" sx={{ textAlign: "center", display: "block" }}>
                🔒 5-minute safety period active before check-out unlocks.
              </Typography>
            )}
          </Box>
        )}

        {status === "COMPLETED" && (
          <Box sx={{ textAlign: "center", py: 1, bgcolor: "success.lighter", borderRadius: 2, color: "success.dark" }}>
            <Typography variant="body2" fontWeight={600}>
              Attendance completed for today.
            </Typography>
          </Box>
        )}
      </Box>
    </Paper>
  );
}
