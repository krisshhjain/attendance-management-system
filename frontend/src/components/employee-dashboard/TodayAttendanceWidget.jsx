import { useCallback, useEffect, useRef, useState } from "react";
import { checkIn, checkOut, getToday } from "../../lib/attendance.js";
import { getCurrentCoordinates } from "../../lib/location.js";
import { ATTENDANCE_GEOFENCE, calculateHaversineDistance } from "../../lib/geofence.js";
import { ApiError } from "../../lib/api.js";
import { StatusBadge } from "../StatusBadge.jsx";
import { ErrorState, LoadingState } from "../States.jsx";
import { Box, Button, Typography, Paper, CircularProgress, Divider } from "@mui/material";
import { FaceVerificationModal } from "./FaceVerificationModal.jsx";
import CameraAltOutlinedIcon from '@mui/icons-material/CameraAltOutlined';

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

  const handleFaceAction = useCallback(async (type) => {
    if (inFlight.current) return;
    inFlight.current = true;
    setPending(true);
    setActionError(null);
    setSuccessMessage(null);
    setPendingText("Verifying location...");

    try {
      const coords = await getCurrentCoordinates();
      
      if (coords.accuracy > ATTENDANCE_GEOFENCE.maxAccuracyMeters) {
        throw new Error("Your location accuracy is too low. Please enable precise location and try again.");
      }

      const distance = calculateHaversineDistance(
        coords.latitude,
        coords.longitude,
        ATTENDANCE_GEOFENCE.latitude,
        ATTENDANCE_GEOFENCE.longitude
      );

      if (distance > ATTENDANCE_GEOFENCE.radiusMeters) {
        throw new Error("You are outside the allowed attendance area. Please move closer to the workplace and try again.");
      }

      setLocationData(coords);
      setFaceModalType(type);
      setFaceModalOpen(true);
    } catch (error) {
      setActionError(
        error instanceof ApiError
          ? error.message
          : error?.message || "Could not verify your location."
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

      {successMessage && (
        <Box
          sx={{
            mb: 2,
            p: 1.5,
            borderRadius: 2,
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
            borderRadius: 2,
            border: "1px solid",
            borderColor: "error.light",
            bgcolor: "rgba(211, 47, 47, 0.05)",
            color: "error.main",
            typography: "body2",
          }}
        >
          {actionError}
        </Box>
      )}

      <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: "auto" }}>
        {status === "NOT_CHECKED_IN" && (
          <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
            <Button
              variant="contained"
              color="primary"
              disabled={pending}
              onClick={() => handleFaceAction("in")}
              fullWidth
              startIcon={<CameraAltOutlinedIcon />}
              sx={{ py: 1.5, fontWeight: 600, borderRadius: 2, textTransform: "none", fontSize: "1rem" }}
            >
              {pending && pendingText.includes("location") ? pendingText : "Face Check-In"}
            </Button>
            
            <Box sx={{ display: 'flex', alignItems: 'center', opacity: 0.6 }}>
              <Divider sx={{ flexGrow: 1 }} />
              <Typography variant="caption" sx={{ px: 2, fontWeight: 600 }}>OR</Typography>
              <Divider sx={{ flexGrow: 1 }} />
            </Box>

            <Button
              variant="outlined"
              color="inherit"
              disabled={pending}
              onClick={() => runAction("in")}
              fullWidth
              sx={{ py: 1, fontWeight: 600, borderRadius: 2, textTransform: "none" }}
            >
              Manual Check-In
            </Button>
          </Box>
        )}

        {status === "CHECKED_IN" && (
          <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
            <Button
              variant="contained"
              color={secondsRemaining > 0 ? "inherit" : "primary"}
              disabled={pending || secondsRemaining > 0}
              onClick={() => handleFaceAction("out")}
              fullWidth
              startIcon={<CameraAltOutlinedIcon />}
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
                ? (pendingText || "Checking out...")
                : secondsRemaining > 0
                ? `Check Out (${Math.floor(secondsRemaining / 60)}:${(secondsRemaining % 60).toString().padStart(2, "0")} resting period)`
                : "Face Check-Out"}
            </Button>
            
            <Box sx={{ display: 'flex', alignItems: 'center', opacity: 0.6 }}>
              <Divider sx={{ flexGrow: 1 }} />
              <Typography variant="caption" sx={{ px: 2, fontWeight: 600 }}>OR</Typography>
              <Divider sx={{ flexGrow: 1 }} />
            </Box>

            <Button
              variant="outlined"
              color="inherit"
              disabled={pending || secondsRemaining > 0}
              onClick={() => runAction("out")}
              fullWidth
              sx={{ py: 1, fontWeight: 600, borderRadius: 2, textTransform: "none" }}
            >
              Manual Check-Out
            </Button>

            {secondsRemaining > 0 && (
              <Typography variant="caption" color="text.secondary" sx={{ textAlign: "center", display: "block" }}>
                🔒 5-minute safety period active before check-out unlocks.
              </Typography>
            )}
          </Box>
        )}

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

        {status === "COMPLETED" && (
          <Box sx={{ textAlign: "center", py: 1, bgcolor: "success.lighter", borderRadius: 2, color: "success.dark" }}>
            <Typography variant="body2" fontWeight={600}>
              Attendance completed for today.
            </Typography>
          </Box>
        )}

        {status === "LEAVE" && (
          <Box sx={{ textAlign: "center", py: 1.5, bgcolor: "info.lighter", borderRadius: 2, color: "info.dark" }}>
            <Typography variant="body2" fontWeight={600}>
              🌴 You are on leave today. Enjoy your time off!
            </Typography>
          </Box>
        )}
      </Box>
    </Paper>
  );
}
