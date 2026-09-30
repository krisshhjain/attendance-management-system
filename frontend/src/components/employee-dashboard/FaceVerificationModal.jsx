import React, { useState } from "react";
import { Dialog, DialogTitle, DialogContent, Box, Typography } from "@mui/material";
import WebcamCapture from "../WebcamCapture.jsx";
import { apiRequest } from "../../lib/api.js";
import { getErrorMessage } from "../../feedback/errorMessage.js";
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import { useFeedback } from "../../feedback/FeedbackProvider.jsx";

export function FaceVerificationModal({ open, onClose, onSuccess, actionType, locationData }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const { success: notifySuccess } = useFeedback();

  const isCheckOut = actionType === "out";
  const endpoint = isCheckOut ? "/attendance/website-facial-check-out/" : "/attendance/website-facial-check-in/";

  const handleCapture = async (images) => {
    if (!images || images.length === 0) return;
    const base64Image = images[0];

    setLoading(true);
    setError(null);

    try {
      await apiRequest(endpoint, {
        method: "POST",
        body: { 
          image: base64Image,
          latitude: locationData?.latitude,
          longitude: locationData?.longitude,
          accuracy: locationData?.accuracy,
        },
      });

      notifySuccess(isCheckOut ? "Checked out successfully." : "Attendance marked successfully.");
      onSuccess();
    } catch (err) {
      let msg = getErrorMessage(err, "An unexpected error occurred.");
      if (msg.includes("multi-face")) msg = "Please make sure only one person is visible.";
      if (msg.includes("No faces detected")) msg = "No face detected. Please position your face inside the frame.";
      if (msg.includes("confidence")) msg = "Please improve lighting and position your face clearly.";
      
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (loading) return; 
    setError(null);
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
        {error && (
          <Box sx={{ mb: 3, p: 2, bgcolor: "error.lighter", color: "error.dark", borderRadius: 2, display: "flex", alignItems: "center", gap: 1, width: "100%" }}>
            <ErrorOutlineIcon fontSize="small" />
            <Typography variant="body2" fontWeight={500}>{error}</Typography>
          </Box>
        )}

        <WebcamCapture
          mode="single"
          purpose="attendance"
          onCapture={handleCapture}
          onCancel={handleClose}
          isLoading={loading}
        />
      </DialogContent>
    </Dialog>
  );
}
