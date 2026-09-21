import { createFileRoute } from "@tanstack/react-router";
import { RequireAuth } from "../components/RequireAuth.jsx";
import { useAuth } from "../lib/auth.jsx";
import { Box, Typography, Paper, Grid2, Card, CardContent } from "@mui/material";

export const Route = createFileRoute("/administration")({
  component: Administration,
});

function Administration() {
  const { user, loginType } = useAuth();

  if (!user?.is_superuser || loginType !== "admin") {
    return (
      <RequireAuth>
        <Box sx={{ p: 4, textAlign: "center", bgcolor: "white", borderRadius: 4, border: "1px solid", borderColor: "divider" }}>
          <Typography variant="h5" fontWeight={600} gutterBottom color="error">
            Access Denied
          </Typography>
          <Typography color="text.secondary">
            You do not have permission to view the administration page.
          </Typography>
        </Box>
      </RequireAuth>
    );
  }

  return (
    <RequireAuth>
      <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 700, letterSpacing: "-0.5px" }}>
            Administration
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Manage system configurations, user roles, and security policies.
          </Typography>
        </Box>

        <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", md: "repeat(4, 1fr)" }, gap: 3 }}>
          {[
            { title: "User & Role Management", desc: "Configure access levels and permissions." },
            { title: "System Configuration", desc: "Manage application settings and preferences." },
            { title: "Security Policies", desc: "Enforce password rules and MFA." },
            { title: "Audit & Logs", desc: "View system events and administrative actions." },
          ].map((item, index) => (
            <Card key={index} elevation={0} sx={{ border: "1px solid", borderColor: "divider", borderRadius: 3 }}>
              <CardContent>
                <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                  {item.title}
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  {item.desc}
                </Typography>
                <Typography variant="caption" sx={{ color: "primary.main", fontWeight: 600, display: "inline-block", p: 0.5, bgcolor: "rgba(125, 37, 169, 0.08)", borderRadius: 1 }}>
                  Coming Soon
                </Typography>
              </CardContent>
            </Card>
          ))}
        </Box>
      </Box>
    </RequireAuth>
  );
}
