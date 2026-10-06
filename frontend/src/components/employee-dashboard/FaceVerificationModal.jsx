import React, { useEffect, useState } from "react";
import { Dialog, DialogTitle, DialogContent, Box, Typography } from "@mui/material";
import WebcamCapture from "../WebcamCapture.jsx";
import { apiRequest } from "../../lib/api.js";
import { getErrorMessage } from "../../feedback/errorMessage.js";
import { useFeedback } from "../../feedback/FeedbackProvider.jsx";
import FaceResultOverlay from "../FaceResultOverlay.jsx";

export function FaceVerificationModal({ open, onClose, onSuccess, actionType, locationData }) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const { success: notifySuccess } = useFeedback();

  useEffect(() => {
    setResult(null);
  }, [open, actionType]);

  const isCheckOut = actionType === "out";
  const endpoint = isCheckOut ? "/attendance/website-facial-check-out/" : "/attendance/website-facial-check-in/";

  const handleCapture = async (images, capturedAtMs) => {
    if (!images || images.length === 0) return;
    setLoading(true);
    setResult(null);

    try {
      await apiRequest(endpoint, {
        method: "POST",
        body: { 
          frames: images,
          captured_at_ms: capturedAtMs,
          latitude: locationData?.latitude,
          longitude: locationData?.longitude,
          accuracy: locationData?.accuracy,
        },
      });

      setResult({ kind: "success", title: "Face verified", message: isCheckOut ? "Check-out complete." : "Check-in complete." });
      await new Promise((resolve) => setTimeout(resolve, 1100));
      notifySuccess(isCheckOut ? "Checked out successfully." : "Attendance marked successfully.");
      onSuccess();
    } catch (err) {
      let msg = getErrorMessage(err, "An unexpected error occurred.");
      if (msg.toLowerCase().includes("liveness check failed")) msg = "We couldn't verify that this is a live camera image. Please try again using your camera.";
      if (msg.toLowerCase().includes("liveness check is temporarily unavailable")) msg = "Live-face verification is temporarily unavailable. Please try again shortly.";
      if (msg.includes("multi-face")) msg = "Please make sure only one person is visible.";
      if (msg.includes("No faces detected")) msg = "No face detected. Please position your face inside the frame.";
      if (msg.includes("confidence")) msg = "Please improve lighting and position your face clearly.";
      
      setResult({ kind: "error", title: "Face not verified", message: msg });
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (loading) return; 
    setResult(null);
    onClose();
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{ sx: { borderRadius: "16px", overflow: "hidden" } }}
    >
      <DialogTitle sx={{ textAlign: "center", pb: 1, pt: 3 }}>
        <Typography variant="h5" fontWeight={700}>Face Verification</Typography>
      </DialogTitle>
      
      <DialogContent sx={{ px: 4, pb: 4, pt: 1, display: "flex", flexDirection: "column", alignItems: "center", minHeight: 450, justifyContent: "center" }}>
        <Box sx={{ position: "relative", display: "grid", placeItems: "center", width: "100%", minHeight: result ? 480 : undefined }}>
          {result ? (
            <FaceResultOverlay {...result} onRetry={() => setResult(null)} onClose={handleClose} />
          ) : (
            <WebcamCapture mode="single" purpose="attendance" onCapture={handleCapture} onCancel={handleClose} isLoading={loading} />
          )}
        </Box>
      </DialogContent>
    </Dialog>
  );
}
