import { createFileRoute } from "@tanstack/react-router";
import { RequireAuth } from "../components/RequireAuth.jsx";
import { useAuth } from "../lib/auth.jsx";
import { Box, Typography } from "@mui/material";
import { EmployeeTable } from "../components/dashboard/EmployeeTable.jsx";

export const Route = createFileRoute("/employees")({
  component: Employees,
});

function Employees() {
  const { user, loginType } = useAuth();

  if (!(user?.is_superuser && loginType === "admin") && loginType !== "systemadmin") {
    return (
      <RequireAuth>
        <Box sx={{ p: 4, textAlign: "center", bgcolor: "white", borderRadius: 4, border: "1px solid", borderColor: "divider" }}>
          <Typography variant="h5" fontWeight={600} gutterBottom color="error">
            Access Denied
          </Typography>
          <Typography color="text.secondary">
            You do not have permission to view this page.
          </Typography>
        </Box>
      </RequireAuth>
    );
  }

  return (
    <RequireAuth>
      <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 700, letterSpacing: "-0.5px", color: "#0f172a", fontSize: "24px" }}>
            Employees
          </Typography>
          <Typography variant="body2" sx={{ color: "#64748b", mt: 0.5, fontSize: "14px" }}>
            View and manage employee details.
          </Typography>
        </Box>
        <EmployeeTable />
      </Box>
    </RequireAuth>
  );
}
