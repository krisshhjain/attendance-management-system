import { useEffect } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useLocation } from "@tanstack/react-router";
import { useAuth } from "../lib/auth.jsx";
import { SuperAdminLayout } from "./SuperAdminLayout.jsx";
import { EmployeeLayout } from "./app/EmployeeLayout.jsx";
import { Alert, Box, CircularProgress } from "@mui/material";
import { ForcePasswordChangeModal } from "./ForcePasswordChangeModal.jsx";

export function RequireAuth({ children }) {
  const { isAuthenticated, ready, user, loginType } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (ready && !isAuthenticated) {
      navigate({ to: "/login", replace: true });
    }
  }, [ready, isAuthenticated, navigate]);

  const effectiveLoginType = loginType || localStorage.getItem("loginType") || "employee";
  const routeAccessKey = {
    "/dashboard": "dashboard",
    "/attendance": "attendance",
    "/leave": "leave",
  }[location.pathname];
  const hasSectionAccess = effectiveLoginType !== "employee"
    || !routeAccessKey
    || (user?.app_access?.[routeAccessKey] !== false);

  useEffect(() => {
    if (ready && isAuthenticated && !hasSectionAccess) {
      const access = user?.app_access || {};
      const firstAllowed = ["dashboard", "attendance", "leave"].find((key) => access[key] !== false);
      if (firstAllowed) navigate({ to: `/${firstAllowed}`, replace: true });
    }
  }, [ready, isAuthenticated, hasSectionAccess, user, navigate]);

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
  const isAdminSession = user?.is_superuser && effectiveLoginType === "admin";
  const isSystemAdminSession = effectiveLoginType === "systemadmin";

  if (!hasSectionAccess) {
    return (
      <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center", p: 3 }}>
        <Alert severity="warning">You don’t have access to this section. Contact your app administrator.</Alert>
      </Box>
    );
  }

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
