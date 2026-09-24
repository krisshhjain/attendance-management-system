import { useCallback, useEffect, useRef, useState } from "react";
import { checkIn, checkOut, getToday } from "../lib/attendance.js";
import { getCurrentCoordinates } from "../lib/location.js";
import { ApiError } from "../lib/api.js";
import { formatDuration, formatTime } from "../lib/date.js";
import { StatusBadge } from "./StatusBadge.jsx";
import { ErrorState, LoadingState } from "./States.jsx";
import {
  Card,
  CardHeader,
  CardContent,
  Typography,
  Box,
  Button,
  Divider,
} from "@mui/material";

export function AttendanceCard({ onChanged }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [actionError, setActionError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [pending, setPending] = useState(false);
  const [pendingText, setPendingText] = useState("");
  const inFlight = useRef(false);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(false);
    try {
      setData(await getToday());
    } catch {
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const runAction = useCallback(
    async (action) => {
      if (inFlight.current) return;
      inFlight.current = true;
      setPending(true);
      setActionError(null);
      setSuccessMessage(null);
      setPendingText("Getting your location...");

      try {
        const coords = await getCurrentCoordinates();
        setPendingText(action === "in" ? "Checking in..." : "Checking out...");
        const res = action === "in" ? await checkIn(coords) : await checkOut(coords);
        setSuccessMessage(
          action === "in"
            ? "Attendance marked successfully."
            : res?.message || "Check-out successful"
        );
        setData(await getToday());
        onChanged?.();
      } catch (error) {
        setActionError(
          error instanceof ApiError
            ? error.message
            : error?.message || "Something went wrong. Please try again."
        );
      } finally {
        inFlight.current = false;
        setPending(false);
        setPendingText("");
      }
    },
    [onChanged],
  );

  const status = data?.status;
  const [secondsRemaining, setSecondsRemaining] = useState(0);

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

  if (loading) return <LoadingState />;
  if (loadError || !data) return <ErrorState onRetry={load} />;

  return (
    <Card variant="outlined" sx={{ borderRadius: 2, boxShadow: "none" }}>
      <CardHeader
        sx={{ borderBottom: "1px solid", borderColor: "divider", pb: 2 }}
        title={
          <Box sx={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
            <Box>
              <Typography variant="h6" sx={{ fontWeight: 600, letterSpacing: "-0.5px" }}>
                Today&rsquo;s Attendance
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                {new Date().toLocaleDateString(undefined, {
                  weekday: "long",
                  day: "2-digit",
                  month: "long",
                  year: "numeric",
                })}
              </Typography>
            </Box>
            <StatusBadge status={status} />
          </Box>
        }
      />

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(3, 1fr)" }, gap: "1px", bgcolor: "divider" }}>
        <Metric label="Check-in" value={formatTime(data.check_in)} />
        <Metric label="Check-out" value={formatTime(data.check_out)} />
        <Metric label="Working hours" value={formatDuration(data.working_duration)} />
      </Box>
      <Divider />

      <CardContent sx={{ pt: 3 }}>
        {successMessage && (
          <Box
            sx={{
              mb: 2,
              p: 1.5,
              borderRadius: 1,
              border: "1px solid",
              borderColor: "success.light",
              bgcolor: "rgba(46, 125, 50, 0.08)",
              color: "success.main",
              typography: "body2",
              fontWeight: 500,
            }}
          >
            {successMessage}
          </Box>
        )}

        {actionError && (
          <Box
            sx={{
              mb: 2,
              p: 1.5,
              borderRadius: 1,
              border: "1px solid",
              borderColor: "error.light",
              bgcolor: "error.50",
              backgroundColor: "rgba(211, 47, 47, 0.05)",
              color: "error.main",
              typography: "body2",
            }}
          >
            {actionError}
          </Box>
        )}

        {status === "NOT_CHECKED_IN" && (
          <ActionButton
            pending={pending}
            label="Check in"
            pendingLabel={pendingText || "Checking in..."}
            onClick={() => runAction("in")}
          />
        )}

        {status === "CHECKED_IN" && (
          <Box sx={{ display: "flex", flexDirection: "column", gap: 1, alignItems: { sm: "flex-start" } }}>
            <ActionButton
              pending={pending}
              disabled={secondsRemaining > 0}
              label={secondsRemaining > 0 ? `Check out (${Math.floor(secondsRemaining / 60)}:${(secondsRemaining % 60).toString().padStart(2, "0")} resting period)` : "Check out"}
              pendingLabel={pendingText || "Checking out..."}
              onClick={() => runAction("out")}
            />
            {secondsRemaining > 0 && (
              <Typography variant="caption" color="text.secondary">
                🔒 5-minute safety period active before check-out unlocks.
              </Typography>
            )}
          </Box>
        )}

        {status === "COMPLETED" && (
          <Typography variant="body2" color="text.secondary">
            Your attendance for today is complete. Have a good evening.
          </Typography>
        )}
      </CardContent>
    </Card>
  );
}

function Metric({ label, value }) {
  return (
    <Box sx={{ bgcolor: "background.paper", px: 3, py: 2.5 }}>
      <Typography variant="caption" sx={{ fontWeight: 500, textTransform: "uppercase", letterSpacing: 1, color: "text.secondary" }}>
        {label}
      </Typography>
      <Typography variant="h5" sx={{ mt: 1, fontWeight: 600, fontFamily: "monospace" }}>
        {value}
      </Typography>
    </Box>
  );
}

function ActionButton({ pending, disabled, label, pendingLabel, onClick }) {
  return (
    <Button
      variant="contained"
      color="primary"
      disabled={pending || disabled}
      onClick={onClick}
      fullWidth
      sx={{
        py: 1.5,
        fontWeight: 600,
        textTransform: "uppercase",
        letterSpacing: 1,
        width: { sm: "auto" }
      }}
    >
      {pending ? pendingLabel : label}
    </Button>
  );
}
