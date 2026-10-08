import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { checkIn, checkOut, getToday } from "../../lib/attendance.js";
import { getCurrentCoordinates } from "../../lib/location.js";
import { ATTENDANCE_GEOFENCE, calculateHaversineDistance, isLocationInsideGeofence } from "../../lib/geofence.js";
import { fetchOfficeLocations } from "../../lib/api.js";
import { StatusBadge } from "../StatusBadge.jsx";
import { ErrorState, LoadingState } from "../States.jsx";
import { Alert, Box, Button, Typography, Paper, CircularProgress, Chip } from "@mui/material";
import { FaceVerificationModal } from "./FaceVerificationModal.jsx";
import CameraAltOutlinedIcon from '@mui/icons-material/CameraAltOutlined';
import ScheduleOutlinedIcon from "@mui/icons-material/ScheduleOutlined";
import { useQuery } from "@tanstack/react-query";
import { fetchMyShift } from "../../lib/api.js";
import { useFeedback } from "../../feedback/FeedbackProvider.jsx";

export function TodayAttendanceWidget({ data, loading, loadError, reloadData }) {
  const navigate = useNavigate();
  const [pending, setPending] = useState(false);
  const [pendingText, setPendingText] = useState("");
  const [secondsRemaining, setSecondsRemaining] = useState(0);
  const [liveWorkingSeconds, setLiveWorkingSeconds] = useState(null);
  const [faceModalOpen, setFaceModalOpen] = useState(false);
  const [faceModalType, setFaceModalType] = useState("in");
  const [locationData, setLocationData] = useState(null);
  const inFlight = useRef(false);
  const { success, notifyError } = useFeedback();

  const { data: shiftData } = useQuery({
    queryKey: ["myShift"],
    queryFn: fetchMyShift,
  });

  const status = data?.status;
  const shift = shiftData?.shift;
  const previousIncomplete = data?.previous_incomplete_attendance;

  const formatAttendanceTime = (value) => {
    if (!value) return "--:--";
    const date = new Date(value);
    return Number.isNaN(date.getTime())
      ? "--:--"
      : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
  };

  const formatWorkingDuration = (value) => {
    if (!value) return "00h 00m";
    if (typeof value === "number") {
      const hours = Math.floor(value / 3600);
      const minutes = Math.floor((value % 3600) / 60);
      return `${String(hours).padStart(2, "0")}h ${String(minutes).padStart(2, "0")}m`;
    }
    if (typeof value === "string" && Number.isFinite(Number(value))) {
      const seconds = Number(value);
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      return `${String(hours).padStart(2, "0")}h ${String(minutes).padStart(2, "0")}m`;
    }
    return value;
  };

  const parseWorkingSeconds = (value) => {
    if (typeof value === "number") return value;
    if (typeof value !== "string") return 0;
    const match = /^(?:(\d+)\s+days?,\s*)?(\d+):(\d{2}):(\d{2})/.exec(value);
    if (!match) return Number(value) || 0;
    return (Number(match[1] || 0) * 86400) + (Number(match[2]) * 3600) + (Number(match[3]) * 60) + Number(match[4]);
  };

  useEffect(() => {
    const activeCheckIn = data?.active_check_in ? new Date(data.active_check_in).getTime() : NaN;
    if (status !== "CHECKED_IN" || !Number.isFinite(activeCheckIn)) {
      setLiveWorkingSeconds(null);
      return;
    }

    const updateLiveDuration = () => {
      const completedSeconds = parseWorkingSeconds(data.completed_working_duration);
      const currentSeconds = Math.max(0, Math.floor((Date.now() - activeCheckIn) / 1000));
      setLiveWorkingSeconds(completedSeconds + currentSeconds);
    };

    updateLiveDuration();
    const interval = setInterval(updateLiveDuration, 1000);
    return () => clearInterval(interval);
  }, [data?.active_check_in, data?.completed_working_duration, status]);

  const workingDisplay = liveWorkingSeconds !== null
    ? formatWorkingDuration(liveWorkingSeconds)
    : formatWorkingDuration(data?.working_duration);

  const handleFaceAction = useCallback(async (type) => {
    if (inFlight.current) return;
    inFlight.current = true;
    setPending(true);
    setPendingText("Verifying location...");

    try {
      const coords = await getCurrentCoordinates();

      if (coords.accuracy > ATTENDANCE_GEOFENCE.maxAccuracyMeters) {
        throw new Error("Your location accuracy is too low. Please enable precise location and try again.");
      }

      let locations = [];
      try {
        locations = await fetchOfficeLocations();
      } catch {
        // The geofence helper falls back to the configured default location.
      }

      if (!isLocationInsideGeofence(coords.latitude, coords.longitude, locations)) {
        throw new Error("You are outside the allowed attendance area. Please move closer to an office location and try again.");
      }

      setLocationData(coords);
      setFaceModalType(type);
      setFaceModalOpen(true);
    } catch (error) {
      notifyError(error, { title: "Location unavailable", fallback: "Could not get your location. Please enable location access and try again." });
    } finally {
      inFlight.current = false;
      setPending(false);
      setPendingText("");
    }
  }, [notifyError]);

  const runAction = useCallback(
    async (action) => {
      if (inFlight.current) return;
      inFlight.current = true;
      setPending(true);
      setPendingText("Getting your location...");

      try {
        const coords = await getCurrentCoordinates();
        setPendingText(action === "in" ? "Checking in..." : "Checking out...");
        await (action === "in" ? checkIn(coords) : checkOut(coords));
        success(action === "in" ? "Attendance marked successfully." : "Checked out successfully.");
        await reloadData();
      } catch (error) {
        notifyError(error, { title: "Attendance unavailable", fallback: "Attendance could not be updated." });
      } finally {
        inFlight.current = false;
        setPending(false);
        setPendingText("");
      }
    },
    [notifyError, reloadData, success],
  );

  if (loading) return <Paper sx={{ p: 4, display: "flex", justifyContent: "center", borderRadius: 3, border: "1px solid", borderColor: "divider", boxShadow: "none" }}><CircularProgress /></Paper>;
  if (loadError || !data) return <ErrorState onRetry={reloadData} />;

  const canCheckIn = status === "NOT_CHECKED_IN" || status === "COMPLETED";
  const canCheckOut = status === "CHECKED_IN";

  return (
    <Paper sx={{ overflow: "visible", height: "auto", borderRadius: 3, border: "1px solid", borderColor: "#dbe3ee", boxShadow: "0 2px 8px rgba(15, 23, 42, 0.06)" }}>
      <Box sx={{ px: { xs: 2, sm: 2.5 }, py: 1.75, borderBottom: "1px solid", borderColor: "#e5ebf2", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2 }}>
        <Box>
          <Typography sx={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color: "#718096" }}>
            Today&apos;s Attendance
          </Typography>
          <Box sx={{ display: "flex", alignItems: "center", gap: 0.8, mt: 0.5 }}>
            <Box sx={{ width: 9, height: 9, borderRadius: "50%", bgcolor: canCheckOut ? "#22c55e" : "#cbd5e1" }} />
            <Typography sx={{ fontSize: 13, fontWeight: 700, color: "#1e293b" }}>
              {status === "HOLIDAY" ? "Holiday" : status === "WEEKEND" ? "Weekend" : status === "LEAVE" ? "On Leave" : canCheckOut ? "Checked In" : status === "COMPLETED" ? "Checked Out" : "Not Checked In"}
            </Typography>
          </Box>
        </Box>
        <StatusBadge status={status} />
      </Box>

      {status === "HOLIDAY" && data.holiday_name && <Typography sx={{ px: 2.5, pt: 1.5, color: "#64748b", fontSize: 13 }}>{data.holiday_name}</Typography>}

      {shift && (
        <Box sx={{ mx: 2.5, mt: 2, display: "flex", alignItems: "center", gap: 1, color: "text.secondary" }}>
          <ScheduleOutlinedIcon sx={{ fontSize: 18 }} />
          <Typography variant="caption" fontWeight={600}>{shift.name}</Typography>
          <Chip label={`${shift.start_time} - ${shift.end_time}`} size="small" sx={{ height: 20, fontSize: 10, fontWeight: 700 }} />
        </Box>
      )}

      {previousIncomplete && (
        <Alert
          severity="warning"
          sx={{ mx: 2.5, mt: 2, alignItems: "center" }}
          action={(
            <Button
              color="inherit"
              size="small"
              onClick={() => navigate({ to: "/regularization" })}
              sx={{ fontWeight: 700, textTransform: "none", whiteSpace: "nowrap" }}
            >
              Regularize
            </Button>
          )}
        >
          Your attendance for {previousIncomplete.date} is incomplete. Please submit a regularization request.
        </Alert>
      )}

      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" } }}>
        <Box sx={{ p: { xs: 2, sm: 2.5 }, display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 1, bgcolor: "#f8fafc", borderRight: { md: "1px solid" }, borderBottom: { xs: "1px solid", md: 0 }, borderColor: "#e5ebf2" }}>
          <Metric label="Check In" value={formatAttendanceTime(data.check_in)} />
          <Metric label="Check Out" value={formatAttendanceTime(data.check_out)} />
          <Metric label="Working" value={workingDisplay} />
        </Box>

        <Box sx={{ p: { xs: 2, sm: 2.5 } }}>
          <Typography sx={{ mb: 1.25, fontSize: 11, fontWeight: 700, letterSpacing: "0.04em", textTransform: "uppercase", color: "#718096" }}>
            Quick Actions
          </Typography>
          <Box sx={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 1 }}>
            <ActionButton label={pending && canCheckIn ? pendingText || "Checking in..." : "Check In"} icon={<ScheduleOutlinedIcon />} primary disabled={!canCheckIn || pending} onClick={() => runAction("in")} />
            <ActionButton label={pending && canCheckOut ? pendingText || "Checking out..." : "Check Out"} icon={<ScheduleOutlinedIcon />} disabled={!canCheckOut || pending} onClick={() => runAction("out")} />
            <ActionButton label={pending && canCheckIn && pendingText.includes("location") ? pendingText : "Face Check In"} icon={<CameraAltOutlinedIcon />} disabled={!canCheckIn || pending} onClick={() => handleFaceAction("in")} />
            <ActionButton label={pending && canCheckOut && pendingText.includes("location") ? pendingText : "Face Check Out"} icon={<CameraAltOutlinedIcon />} disabled={!canCheckOut || pending} onClick={() => handleFaceAction("out")} />
          </Box>
        </Box>
      </Box>

      <FaceVerificationModal
        open={faceModalOpen}
        actionType={faceModalType}
        locationData={locationData}
        onClose={() => setFaceModalOpen(false)}
        onSuccess={() => {
          setFaceModalOpen(false);
          reloadData();
        }}
      />
    </Paper>
  );
}

function Metric({ label, value }) {
  return (
    <Box sx={{ minWidth: 0, px: { xs: 0.5, sm: 1 }, borderRight: "1px solid", borderColor: "#e2e8f0", "&:last-child": { borderRight: 0 } }}>
      <Typography sx={{ fontSize: 11, color: "#718096", mb: 0.5 }}>{label}</Typography>
      <Typography sx={{ fontSize: { xs: 13, sm: 15 }, fontWeight: 700, color: "#334155", whiteSpace: "nowrap" }}>{value}</Typography>
    </Box>
  );
}

function ActionButton({ label, icon, primary = false, disabled, onClick }) {
  return (
    <Button
      variant={primary ? "contained" : "outlined"}
      disabled={disabled}
      onClick={onClick}
      startIcon={icon}
      fullWidth
      sx={{
        minHeight: 38,
        px: 1,
        borderRadius: 1.5,
        borderColor: "#dbe3ee",
        color: primary ? "#fff" : "#64748b",
        bgcolor: primary ? "#4f39ee" : "#fff",
        fontSize: { xs: 11, sm: 12 },
        fontWeight: 700,
        textTransform: "none",
        whiteSpace: "nowrap",
        boxShadow: "none",
        "&:hover": {
          bgcolor: primary ? "#4338ca" : "#f8fafc",
          borderColor: "#cbd5e1",
        },
        "&.Mui-disabled": {
          color: "#94a3b8",
          borderColor: "#e2e8f0",
          bgcolor: primary ? "#e2e8f0" : "#f8fafc",
          boxShadow: "none",
          opacity: 1,
        },
      }}
    >
      {label}
    </Button>
  );
}
