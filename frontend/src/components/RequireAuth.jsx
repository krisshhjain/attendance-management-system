import { useEffect } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useAuth } from "../lib/auth.jsx";
import { SuperAdminLayout } from "./SuperAdminLayout.jsx";
import { EmployeeLayout } from "./app/EmployeeLayout.jsx";
import { Box, CircularProgress } from "@mui/material";
import { ForcePasswordChangeModal } from "./ForcePasswordChangeModal.jsx";

export function RequireAuth({ children }) {
  const { isAuthenticated, ready, user, loginType } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (ready && !isAuthenticated) {
      navigate({ to: "/login", replace: true });
    }
  }, [ready, isAuthenticated, navigate]);

  if (!ready || !isAuthenticated) {
    return (
      <Box
        sx={{
          display: "flex",
          minHeight: "100vh",
          alignItems: "center",
          justifyContent: "center",
          bgcolor: "background.default",
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  // Double-check localStorage directly to avoid any stale-state flash.
  // loginType from context and localStorage should always agree, but
  // reading both ensures we never render the wrong layout on a hot reload
  const effectiveLoginType = loginType || localStorage.getItem("loginType") || "employee";
  const isAdminSession = user?.is_superuser && effectiveLoginType === "admin";
  const isSystemAdminSession = effectiveLoginType === "systemadmin";

  return (
    <>
      {user?.must_change_password && <ForcePasswordChangeModal open={true} />}
      {isSystemAdminSession ? (
        <SuperAdminLayout>{children}</SuperAdminLayout>
      ) : isAdminSession ? (
        <SuperAdminLayout>{children}</SuperAdminLayout>
      ) : (
        <EmployeeLayout>{children}</EmployeeLayout>
      )}
    </>
  );
}
