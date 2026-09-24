import React, { useState } from "react";
import { Dialog, DialogTitle, DialogContent, Box, Typography, Button, CircularProgress } from "@mui/material";
import WebcamCapture from "../WebcamCapture.jsx";
import { apiRequest } from "../../lib/api.js";
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';

export function FaceVerificationModal({ open, onClose, onSuccess, actionType, locationData }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  const isCheckOut = actionType === "out";
  const endpoint = isCheckOut ? "/attendance/website-facial-check-out/" : "/attendance/website-facial-check-in/";
  const successText = isCheckOut ? "Check-out successful" : "Check-in successful";
  const subText = isCheckOut ? "Have a great rest of your day!" : "You're all set for today.";

  const handleCapture = async (images) => {
    if (!images || images.length === 0) return;
    const base64Image = images[0];

    setLoading(true);
    setError(null);
    setSuccess(false);

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

      setSuccess(true);
      setTimeout(() => {
        setSuccess(false);
        onSuccess();
      }, 2000);
    } catch (err) {
      let msg = err.message || "An unexpected error occurred.";
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
    setSuccess(false);
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
        {success ? (
          <Box sx={{ py: 6, display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
            <CheckCircleOutlineIcon color="success" sx={{ fontSize: 64 }} />
            <Typography variant="h6" color="success.main" fontWeight={600}>{successText}</Typography>
            <Typography variant="body2" color="text.secondary">{subText}</Typography>
          </Box>
        ) : (
          <>
            {error && (
              <Box sx={{ mb: 3, p: 2, bgcolor: "error.lighter", color: "error.dark", borderRadius: 2, display: "flex", alignItems: "center", gap: 1, width: "100%" }}>
                <ErrorOutlineIcon fontSize="small" />
                <Typography variant="body2" fontWeight={500}>{error}</Typography>
              </Box>
            )}

            <WebcamCapture
              mode="single"
              onCapture={handleCapture}
              onCancel={handleClose}
              isLoading={loading}
            />
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
