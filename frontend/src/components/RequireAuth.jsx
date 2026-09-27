import { useEffect, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { useLocation } from "@tanstack/react-router";
import { useAuth } from "../lib/auth.jsx";
import { SuperAdminLayout } from "./SuperAdminLayout.jsx";
import { EmployeeLayout } from "./app/EmployeeLayout.jsx";
import { Alert, Box, Button, CircularProgress, Typography } from "@mui/material";
import { ForcePasswordChangeModal } from "./ForcePasswordChangeModal.jsx";
import { ShiftSelectionScreen } from "./ShiftSelectionScreen.jsx";
import { useQuery } from "@tanstack/react-query";
import { fetchMyShift } from "../lib/api.js";

export function RequireAuth({ children }) {
  const { isAuthenticated, ready, user, loginType } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // Local flag: set to true once this session has confirmed a shift is present.
  // This lets the gate disappear immediately after assignment without a full
  // page reload.
  const [shiftConfirmed, setShiftConfirmed] = useState(false);

  useEffect(() => {
    if (ready && !isAuthenticated) {
      navigate({ to: "/login", replace: true });
    }
  }, [ready, isAuthenticated, navigate]);

  const effectiveLoginType = loginType || localStorage.getItem("loginType") || "employee";
  const isEmployeeSession =
    effectiveLoginType === "employee" &&
    !user?.is_superuser &&
    !user?.is_staff;

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

  // Fetch shift only for plain employee sessions; skip for admin/system-admin.
  const {
    data: myShiftData,
    isLoading: shiftLoading,
    isError: shiftError,
    refetch: refetchShift,
  } = useQuery({
    queryKey: ["myShift"],
    queryFn: fetchMyShift,
    // Only run after auth is ready and this is a plain employee session
    enabled: ready && isAuthenticated && isEmployeeSession && !shiftConfirmed,
    // Retry once; after that surface the error — do not silently block forever
    retry: 1,
    staleTime: 60_000,
  });

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
        <Alert severity="warning">You don't have access to this section. Contact your app administrator.</Alert>
      </Box>
    );
  }

  // ── Shift gate (employee-only) ─────────────────────────────────────────
  if (isEmployeeSession && !shiftConfirmed) {
    // 1. Still in-flight — show spinner
    if (shiftLoading) {
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

    // 2. Fetch failed — BLOCKED. Never allow dashboard access.
    if (shiftError) {
      return (
        <Box
          sx={{
            display: "flex",
            flexDirection: "column",
            minHeight: "100vh",
            alignItems: "center",
            justifyContent: "center",
            bgcolor: "background.default",
            gap: 2,
            px: 2,
          }}
        >
          <Alert
            severity="error"
            sx={{ maxWidth: 420, width: "100%" }}
          >
            <Typography variant="body2" fontWeight={600} gutterBottom>
              Could not verify your shift assignment.
            </Typography>
            <Typography variant="body2">
              Please check your connection and try again. You must have a
              shift assigned before accessing the dashboard.
            </Typography>
          </Alert>
          <Button
            variant="contained"
            onClick={() => refetchShift()}
            sx={{ borderRadius: "10px", fontWeight: 600, textTransform: "none" }}
          >
            Retry
          </Button>
        </Box>
      );
    }

    // 3. No shift assigned — show selection screen
    if (!myShiftData?.shift) {
      return (
        <ShiftSelectionScreen
          onAssigned={() => setShiftConfirmed(true)}
        />
      );
    }

    // 4. Shift confirmed by API — fall through to normal layout
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
