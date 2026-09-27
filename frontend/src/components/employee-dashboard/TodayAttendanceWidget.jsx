import { useCallback, useEffect, useRef, useState } from "react";
import { checkIn, checkOut, getToday } from "../../lib/attendance.js";
import { getCurrentCoordinates } from "../../lib/location.js";
import { ATTENDANCE_GEOFENCE, calculateHaversineDistance } from "../../lib/geofence.js";
import { ApiError } from "../../lib/api.js";
import { StatusBadge } from "../StatusBadge.jsx";
import { ErrorState, LoadingState } from "../States.jsx";
import { Box, Button, Typography, Paper, CircularProgress, Chip } from "@mui/material";
import { FaceVerificationModal } from "./FaceVerificationModal.jsx";
import CameraAltOutlinedIcon from '@mui/icons-material/CameraAltOutlined';
import ScheduleOutlinedIcon from "@mui/icons-material/ScheduleOutlined";
import { useQuery } from "@tanstack/react-query";
import { fetchMyShift } from "../../lib/api.js";

export function TodayAttendanceWidget({ data, loading, loadError, reloadData }) {
  const [actionError, setActionError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);
  const [pending, setPending] = useState(false);
  const [pendingText, setPendingText] = useState("");
  const [secondsRemaining, setSecondsRemaining] = useState(0);
  const [faceModalOpen, setFaceModalOpen] = useState(false);
  const [faceModalType, setFaceModalType] = useState("in");
  const [locationData, setLocationData] = useState(null);
  const inFlight = useRef(false);

  const { data: shiftData } = useQuery({
    queryKey: ["myShift"],
    queryFn: fetchMyShift,
  });

  const status = data?.status;
  const shift = shiftData?.shift;

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

  const liveCheckInTime = data?.check_in ? new Date(data.check_in).getTime() : NaN;
  const hasOpenAttendance = Boolean(data?.check_in && !data?.check_out && Number.isFinite(liveCheckInTime));
  const liveWorkingDuration = hasOpenAttendance
    ? Math.max(0, Math.floor((Date.now() - liveCheckInTime) / 1000))
    : null;
  const workingDisplay = liveWorkingDuration !== null
    ? formatWorkingDuration(liveWorkingDuration)
    : formatWorkingDuration(data?.working_duration);

  const handleFaceAction = useCallback(async (type) => {
    if (inFlight.current) return;
    inFlight.current = true;
    setPending(true);
    setActionError(null);
    setSuccessMessage(null);
    setPendingText("Getting location...");

    try {
      const coords = await getCurrentCoordinates();
      
      // Store location data and proceed to face capture
      // Backend will validate geofence
      setLocationData(coords);
      setFaceModalType(type);
      setFaceModalOpen(true);
    } catch (error) {
      setActionError(
        error instanceof ApiError
          ? error.message
          : error?.message || "Could not get your location. Please enable location access and try again."
      );
    } finally {
      inFlight.current = false;
      setPending(false);
      setPendingText("");
    }
  }, []);

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
        await reloadData();
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
    [reloadData],
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
              {status === "LEAVE" ? "On Leave" : canCheckOut ? "Checked In" : status === "COMPLETED" ? "Checked Out" : "Not Checked In"}
            </Typography>
          </Box>
        </Box>
        <StatusBadge status={status} />
      </Box>

      {successMessage && <Box sx={{ mx: 2.5, mt: 2, p: 1.25, borderRadius: 1.5, bgcolor: "rgba(46, 125, 50, 0.08)", color: "success.main", typography: "body2", fontWeight: 600 }}>{successMessage}</Box>}
      {actionError && <Box sx={{ mx: 2.5, mt: 2, p: 1.25, borderRadius: 1.5, bgcolor: "rgba(211, 47, 47, 0.06)", color: "error.main", typography: "body2" }}>{actionError}</Box>}

      {shift && (
        <Box sx={{ mx: 2.5, mt: 2, display: "flex", alignItems: "center", gap: 1, color: "text.secondary" }}>
          <ScheduleOutlinedIcon sx={{ fontSize: 18 }} />
          <Typography variant="caption" fontWeight={600}>{shift.name}</Typography>
          <Chip label={`${shift.start_time} - ${shift.end_time}`} size="small" sx={{ height: 20, fontSize: 10, fontWeight: 700 }} />
        </Box>
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
