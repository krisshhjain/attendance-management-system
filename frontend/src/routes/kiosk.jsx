import React, { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Box, Typography, Button, Paper } from "@mui/material";
import WebcamCapture from "../components/WebcamCapture.jsx";
import FaceResultOverlay from "../components/FaceResultOverlay.jsx";
import { useFeedback } from "../feedback/FeedbackProvider.jsx";

export const Route = createFileRoute("/kiosk")({
  component: Kiosk,
});

function Kiosk() {
  const [loading, setLoading] = useState(false);
  const [actionType, setActionType] = useState(null); // 'check-in' or 'check-out'
  const [result, setResult] = useState(null);
  const { success, info } = useFeedback();

  const processFaceAction = async (images, capturedAtMs) => {
    if (images.length === 0 || !actionType) return;
    
    setLoading(true);
    setResult(null);
    try {
      const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api';
      const endpoint = actionType === 'check-in' ? '/attendance/kiosk/check-in/' : '/attendance/kiosk/check-out/';
      
      const res = await fetch(`${baseUrl}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ frames: images, captured_at_ms: capturedAtMs }),
        // No Authorization header needed since it's a public/kiosk endpoint
      });
      
      const data = await res.json();
      
      if (!res.ok) {
        throw new Error(data.error || "Action failed");
      }
      
      setResult({ kind: "success", title: "Face verified", message: actionType === "check-in" ? "Check-in complete." : "Check-out complete." });
      await new Promise((resolve) => setTimeout(resolve, 1100));
      success(actionType === "check-in" ? "Attendance marked successfully." : "Checked out successfully.");
      setResult(null);
      setActionType(null);
      
    } catch (err) {
      const message = err?.message || "";
      if (message.toLowerCase().includes("liveness check failed")) {
        setResult({ kind: "error", title: "Face not verified", message: "We couldn't verify that this is a live camera image. Please try again using the kiosk camera." });
      } else if (message.toLowerCase().includes("liveness check is temporarily unavailable")) {
        setResult({ kind: "error", title: "Verification unavailable", message: "Live-face verification is temporarily unavailable. Please try again shortly." });
      } else {
        setResult({ kind: "error", title: "Attendance not completed", message: err?.message || "Kiosk attendance could not be completed." });
      }
    } finally {
      setLoading(false);
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

        <Box sx={{ position: "relative", display: "grid", placeItems: "center", minHeight: result ? 480 : undefined, mb: 4 }}>
          {!result && <WebcamCapture 
            mode="single"
            purpose="attendance"
            onCapture={processFaceAction}
            onCancel={() => { setActionType(null); setResult(null); }}
            isLoading={loading}
          />}
          {result && <FaceResultOverlay
            {...result}
            onRetry={() => setResult(null)}
            onClose={() => { setResult(null); setActionType(null); }}
          />}
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
              info("Press Capture & Verify to check in.");
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
              info("Press Capture & Verify to check out.");
            }}
            sx={{ px: 6, py: 2, fontSize: "1.2rem", borderRadius: 2 }}
            disabled={loading}
          >
            Check Out
          </Button>
        </Box>
      </Paper>

    </Box>
  );
}
