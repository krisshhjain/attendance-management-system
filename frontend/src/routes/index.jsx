import { useEffect } from "react";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useAuth } from "../lib/auth.jsx";
import { Box, CircularProgress } from "@mui/material";

export const Route = createFileRoute("/")({
  component: Index,
});

function Index() {
  const { isAuthenticated, ready } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (ready) {
      navigate({ to: isAuthenticated ? "/dashboard" : "/login", replace: true });
    }
  }, [ready, isAuthenticated, navigate]);

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", alignItems: "center", justifyContent: "center", bgcolor: "background.default" }}>
      <CircularProgress />
    </Box>
  );
}
