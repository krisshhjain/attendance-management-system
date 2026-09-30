import React, { useState } from "react";
import { Dialog, DialogTitle, DialogContent, Box, Typography } from "@mui/material";
import WebcamCapture from "../WebcamCapture.jsx";
import { apiRequest } from "../../lib/api.js";
import { getErrorMessage } from "../../feedback/errorMessage.js";
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import { useFeedback } from "../../feedback/FeedbackProvider.jsx";

export function FaceCheckInModal({ open, onClose, onSuccess }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const { success: notifySuccess } = useFeedback();

  const handleCapture = async (images) => {
    if (!images || images.length === 0) return;
    const base64Image = images[0];

    setLoading(true);
    setError(null);

    try {
      // Convert base64 to Blob if backend expects form data, 
      // but WebsiteFacialCheckInView expects JSON {"image": "..."} because it uses request.data.get("image")
      // Wait, let's verify what WebsiteFacialCheckInView expects.
      // request.data.get("image") in DRF works with JSON.
      // We will send JSON.
      
      await apiRequest("/attendance/website-facial-check-in/", {
        method: "POST",
        body: { image: base64Image },
      });

      notifySuccess("Attendance marked successfully.");
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
    if (loading) return; // Prevent closing while processing
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
      
      <DialogContent sx={{ px: 4, pb: 4, pt: 1, display: "flex", flexDirection: "column", alignItems: "center" }}>
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
