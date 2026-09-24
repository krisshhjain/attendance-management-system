import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useAuth } from "../lib/auth.jsx";
import {
  Box,
  Typography,
  Card,
  CardContent,
  TextField,
  Button,
  ToggleButton,
  ToggleButtonGroup,
  InputAdornment,
  IconButton,
  Avatar,
} from "@mui/material";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign in — AttendPro Attendance" },
      {
        name: "description",
        content: "Employee sign in for AttendPro attendance and leave management.",
      },
      { property: "og:title", content: "Sign in — AttendPro Attendance" },
      {
        property: "og:description",
        content: "Employee sign in for AttendPro attendance and leave management.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const { login, isAuthenticated, ready } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [userType, setUserType] = useState("employee");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (ready && isAuthenticated) {
      navigate({ to: "/dashboard", replace: true });
    }
  }, [ready, isAuthenticated, navigate]);

  async function handleSubmit(event) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await login(email.trim(), password, userType);
      navigate({ to: "/dashboard", replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid email or password.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Box sx={{ display: "flex", minHeight: "100vh", alignItems: "center", justifyContent: "center", bgcolor: "background.default", px: 2, py: 6 }}>
      <Box sx={{ width: "100%", maxWidth: 400 }}>
        <Box sx={{ mb: 4, display: "flex", alignItems: "center", gap: 2 }}>
          <Avatar sx={{ width: 40, height: 40, bgcolor: "primary.main", fontWeight: "bold", borderRadius: 1 }}>
            A
          </Avatar>
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 600, letterSpacing: "-0.5px", lineHeight: 1.2 }}>
              AttendPro
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Attendance & Leave Management
            </Typography>
          </Box>
        </Box>

        <Card variant="outlined" sx={{ borderRadius: 2, boxShadow: "none" }}>
          <CardContent sx={{ p: 4 }}>
            <Typography variant="h6" sx={{ fontWeight: 600, letterSpacing: "-0.5px" }}>
              Sign in
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
              Choose your user type and sign in with your company credentials.
            </Typography>

            <Box component="form" onSubmit={handleSubmit} sx={{ mt: 3, display: "flex", flexDirection: "column", gap: 2.5 }}>
              <ToggleButtonGroup
                exclusive
                fullWidth
                color="primary"
                value={userType}
                onChange={(_, value) => {
                  if (value) setUserType(value);
                }}
                aria-label="User type"
                sx={{
                  p: 0.5,
                  gap: 0.5,
                  border: "1px solid",
                  borderColor: "divider",
                  borderRadius: 3,
                  bgcolor: "action.hover",
                  "& .MuiToggleButtonGroup-grouped": {
                    flex: 1,
                    border: 0,
                    borderRadius: "10px !important",
                    color: "text.secondary",
                    fontWeight: 600,
                    py: 1.1,
                    textTransform: "none",
                    transition: "background-color 160ms ease, color 160ms ease, box-shadow 160ms ease",
                    "&:hover": { bgcolor: "action.selected" },
                    "&.Mui-selected": {
                      bgcolor: "background.paper",
                      color: "primary.main",
                      boxShadow: "0 1px 4px rgba(0,0,0,0.14)",
                      "&:hover": { bgcolor: "background.paper" },
                    },
                  },
                }}
              >
                <ToggleButton value="employee" aria-label="Employee">Employee</ToggleButton>
                <ToggleButton value="systemadmin" aria-label="System Admin">System Admin</ToggleButton>
              </ToggleButtonGroup>

              <TextField
                label="Email"
                type="email"
                required
                fullWidth
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="employee@example.com"
                InputLabelProps={{ shrink: true }}
              />

              <TextField
                label="Password"
                type={showPassword ? "text" : "password"}
                required
                fullWidth
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                InputLabelProps={{ shrink: true }}
                InputProps={{
                  endAdornment: (
                    <InputAdornment position="end">
                      <Button
                        size="small"
                        onClick={() => setShowPassword((v) => !v)}
                        sx={{ minWidth: "auto", textTransform: "none", color: "text.secondary", fontSize: "0.75rem" }}
                      >
                        {showPassword ? "Hide" : "Show"}
                      </Button>
                    </InputAdornment>
                  ),
                }}
              />

              {error && (
                <Box
                  sx={{
                    p: 1.5,
                    borderRadius: 1,
                    border: "1px solid",
                    borderColor: "error.light",
                    bgcolor: "error.50",
                    backgroundColor: "rgba(211, 47, 47, 0.05)",
                    color: "error.main",
                    typography: "body2",
                  }}
                >
                  {error}
                </Box>
              )}

              <Button
                type="submit"
                variant="contained"
                color="primary"
                fullWidth
                disabled={submitting}
                sx={{ py: 1.5, mt: 1, fontWeight: 600, letterSpacing: 1 }}
              >
                {submitting ? "Signing in..." : "Sign in"}
              </Button>
            </Box>
          </CardContent>
        </Card>

        <Typography variant="caption" display="block" textAlign="center" color="text.secondary" sx={{ mt: 4 }}>
          Trouble signing in? Contact your HR administrator.
        </Typography>
      </Box>
    </Box>
  );
}
