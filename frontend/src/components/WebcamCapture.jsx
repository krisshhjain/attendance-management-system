import React, { useRef, useCallback, useState, useEffect } from "react";
import Webcam from "react-webcam";
import { Box, Button, Typography, CircularProgress } from "@mui/material";

export default function WebcamCapture({ mode = "single", onCapture, onCancel, isLoading }) {
  const webcamRef = useRef(null);
  const [capturedImages, setCapturedImages] = useState([]);
  const [isCapturing, setIsCapturing] = useState(false);
  const [captureCount, setCaptureCount] = useState(0);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      setIsCapturing(false);
    };
  }, []);

  const captureSingle = useCallback(() => {
    const imageSrc = webcamRef.current?.getScreenshot();
    if (imageSrc) {
      onCapture([imageSrc]);
    }
  }, [onCapture]);

  const captureBurst = useCallback(() => {
    if (isCapturing || isLoading) return;
    
    setIsCapturing(true);
    setCaptureCount(0);
    let images = [];
    let count = 0;
    
    // Capture 3 images with a small delay between them
    const interval = setInterval(() => {
      if (webcamRef.current) {
        const imageSrc = webcamRef.current.getScreenshot();
        if (imageSrc) {
          images.push(imageSrc);
        }
      }
      count++;
      setCaptureCount(count);
      
      if (count >= 3) {
        clearInterval(interval);
        setIsCapturing(false);
        setCapturedImages(images);
        onCapture(images);
      }
    }, 1000); // 1000ms between shots to allow for slight pose variations
  }, [isCapturing, isLoading, onCapture]);

  return (
    <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2 }}>
      <Typography variant="body1" color="text.secondary" align="center" sx={{ maxWidth: 400 }}>
        {mode === "burst" 
          ? "Position face within the frame. The system will capture 3 samples automatically." 
          : "Position face clearly within the frame."}
      </Typography>
      
      <Box sx={{ 
        position: "relative", 
        width: "100%", 
        maxWidth: 640, 
        height: 480, 
        backgroundColor: "#000",
        borderRadius: 2,
        overflow: "hidden" 
      }}>
        <Webcam
          audio={false}
          ref={webcamRef}
          screenshotFormat="image/jpeg"
          videoConstraints={{
            width: 640,
            height: 480,
            facingMode: "user"
          }}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
        
        {/* Subtle Targeting Overlay */}
        <Box sx={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          width: "250px",
          height: "350px",
          border: "2px dashed rgba(255, 255, 255, 0.5)",
          borderRadius: "50%",
          pointerEvents: "none",
          boxShadow: "0 0 0 9999px rgba(0, 0, 0, 0.3)"
        }} />

        {(isLoading || isCapturing) && (
          <Box sx={{
            position: "absolute",
            top: 0, left: 0, right: 0, bottom: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: "rgba(0,0,0,0.6)",
            color: "white",
            zIndex: 10
          }}>
            <CircularProgress color="inherit" size={48} sx={{ mb: 2 }} />
            <Typography variant="h5" sx={{ fontWeight: 600 }}>
              {isCapturing 
                ? `Capturing... ${captureCount}/3` 
                : "Processing Enrollment..."}
            </Typography>
            {isCapturing && (
              <Typography variant="body1" sx={{ mt: 1, opacity: 0.8 }}>
                Please hold still
              </Typography>
            )}
          </Box>
        )}
      </Box>
      
      <Box sx={{ display: "flex", gap: 2, mt: 2 }}>
        <Button 
          variant="outlined" 
          color="secondary" 
          onClick={onCancel}
          disabled={isLoading || isCapturing}
        >
          Cancel
        </Button>
        <Button 
          variant="contained" 
          color="primary" 
          onClick={mode === "burst" ? captureBurst : captureSingle}
          disabled={isLoading || isCapturing}
        >
          {mode === "burst" ? "Start Capture" : "Capture & Verify"}
        </Button>
      </Box>
    </Box>
  );
}
