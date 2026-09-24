import React, { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Box, Typography, Button, Paper, Alert, Snackbar } from "@mui/material";
import WebcamCapture from "../components/WebcamCapture.jsx";

export const Route = createFileRoute("/kiosk")({
  component: Kiosk,
});

function Kiosk() {
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState({ open: false, message: "", severity: "info" });
  const [actionType, setActionType] = useState(null); // 'check-in' or 'check-out'

  const handleCloseNotification = () => {
    setNotification({ ...notification, open: false });
  };

  const showNotification = (message, severity) => {
    setNotification({ open: true, message, severity });
  };

  const processFaceAction = async (images) => {
    if (images.length === 0 || !actionType) return;
    
    setLoading(true);
    try {
      const img = images[0];
      const formData = new FormData();
      
      const split = img.split(',');
      const byteString = atob(split[1]);
      const mimeString = split[0].split(':')[1].split(';')[0];
      const ab = new ArrayBuffer(byteString.length);
      const ia = new Uint8Array(ab);
      for (let i = 0; i < byteString.length; i++) {
        ia[i] = byteString.charCodeAt(i);
      }
      const blob = new Blob([ab], { type: mimeString });
      formData.append("image", blob, "face.jpg");

      const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api';
      const endpoint = actionType === 'check-in' ? '/attendance/kiosk/check-in/' : '/attendance/kiosk/check-out/';
      
      const res = await fetch(`${baseUrl}${endpoint}`, {
        method: "POST",
        body: formData,
        // No Authorization header needed since it's a public/kiosk endpoint
      });
      
      const data = await res.json();
      
      if (!res.ok) {
        throw new Error(data.error || "Action failed");
      }
      
      showNotification(data.message, "success");
      
    } catch (err) {
      showNotification(err.message, "error");
    } finally {
      setLoading(false);
      setActionType(null);
    }
  };

  return (
    <Box sx={{ 
      minHeight: "100vh", 
      display: "flex", 
      flexDirection: "column", 
      alignItems: "center", 
      justifyContent: "center",
      bgcolor: "background.default",
      p: 3
    }}>
      <Paper elevation={3} sx={{ p: 4, borderRadius: 4, maxWidth: 800, width: "100%", textAlign: "center" }}>
        <Typography variant="h3" fontWeight={700} gutterBottom color="primary.main">
          Company Attendance Kiosk
        </Typography>
        <Typography variant="h6" color="text.secondary" sx={{ mb: 4 }}>
          Please align your face in the camera and select an action below.
        </Typography>

        <Box sx={{ display: "flex", justifyContent: "center", mb: 4 }}>
          <WebcamCapture 
            mode="single"
            onCapture={processFaceAction}
            onCancel={() => setActionType(null)}
            isLoading={loading}
          />
        </Box>

        <Box sx={{ display: "flex", justifyContent: "center", gap: 3, mt: 2 }}>
          <Button 
            variant="contained" 
            color="success" 
            size="large"
            onClick={() => {
              setActionType('check-in');
              // The button press sets the action type, but we actually need the WebcamCapture 
              // to trigger the capture. We will just show a tip.
              showNotification("Please press 'Capture & Verify' to Check In", "info");
            }}
            sx={{ px: 6, py: 2, fontSize: "1.2rem", borderRadius: 2 }}
            disabled={loading}
          >
            Check In
          </Button>
          <Button 
            variant="contained" 
            color="warning" 
            size="large"
            onClick={() => {
              setActionType('check-out');
              showNotification("Please press 'Capture & Verify' to Check Out", "info");
            }}
            sx={{ px: 6, py: 2, fontSize: "1.2rem", borderRadius: 2 }}
            disabled={loading}
          >
            Check Out
          </Button>
        </Box>
      </Paper>

      <Snackbar 
        open={notification.open} 
        autoHideDuration={6000} 
        onClose={handleCloseNotification}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={handleCloseNotification} severity={notification.severity} sx={{ width: '100%', fontSize: '1.2rem', py: 2, px: 4 }}>
          {notification.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
