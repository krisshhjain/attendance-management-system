import { useCallback, useEffect, useRef, useState } from "react";
import { checkIn, checkOut, getToday } from "../../lib/attendance.js";
import { getCurrentCoordinates } from "../../lib/location.js";
import { ATTENDANCE_GEOFENCE, calculateHaversineDistance } from "../../lib/geofence.js";
import { ApiError } from "../../lib/api.js";
import { StatusBadge } from "../StatusBadge.jsx";
import { ErrorState, LoadingState } from "../States.jsx";
import { Box, Button, Typography, Paper, CircularProgress, Divider, Chip } from "@mui/material";
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

  return (
    <Paper sx={{ p: 3, borderRadius: 3, border: "1px solid", borderColor: "divider", boxShadow: "none", height: "100%", display: "flex", flexDirection: "column" }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: 2 }}>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 600, letterSpacing: "-0.5px" }}>
            Attendance
          </Typography>
        </Box>
        <StatusBadge status={status} />
      </Box>

      {shift && (
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 3, p: 1.5, bgcolor: "background.default", borderRadius: 2, border: "1px solid", borderColor: "divider" }}>
          <ScheduleOutlinedIcon sx={{ color: "text.secondary", fontSize: 20 }} />
          <Box sx={{ display: "flex", alignItems: "center", gap: 1, flexWrap: "wrap" }}>
            <Typography variant="body2" fontWeight={600} color="text.primary">
              {shift.name}
            </Typography>
            <Chip label={shift.code} size="small" sx={{ height: 20, fontSize: "0.65rem", fontWeight: 700 }} />
            <Typography variant="body2" color="text.secondary">
              ({shift.start_time} - {shift.end_time})
            </Typography>
          </Box>
        </Box>
      )}

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
        {(status === "NOT_CHECKED_IN" || status === "COMPLETED") && (
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
              color="primary"
              disabled={pending}
              onClick={() => handleFaceAction("out")}
              fullWidth
              startIcon={<CameraAltOutlinedIcon />}
              sx={{
                py: 1.5,
                fontWeight: 600,
                borderRadius: 2,
                textTransform: "none",
                fontSize: "1rem",
              }}
            >
              {pending ? (pendingText || "Checking out...") : "Face Check-Out"}
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
              onClick={() => runAction("out")}
              fullWidth
              sx={{ py: 1, fontWeight: 600, borderRadius: 2, textTransform: "none" }}
            >
              Manual Check-Out
            </Button>
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


        {status === "LEAVE" && (
          <Box sx={{ textAlign: "center", py: 1.5, bgcolor: "info.lighter", borderRadius: 2, color: "info.dark" }}>
            <Typography variant="body2" fontWeight={600}>
              🌴 You are on leave today. Enjoy your time off!
            </Typography>
          </Box>
        )}

        {status === "HOLIDAY" && (
          <Box sx={{ textAlign: "center", py: 1.5, bgcolor: "warning.lighter", borderRadius: 2, color: "warning.dark" }}>
            <Typography variant="body2" fontWeight={600}>
              🎉 It's a weekend/holiday. Enjoy your time off!
            </Typography>
          </Box>
        )}
      </Box>
    </Paper>
  );
}
