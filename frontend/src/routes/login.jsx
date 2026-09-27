import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useAuth } from "../lib/auth.jsx";
import {
  Box,
  Typography,
  TextField,
  Button,
  InputAdornment,
} from "@mui/material";

const INK = "#12141F";
const PAPER = "#F6F4EF";
const PAGE_BG = "#EDEAE2";
const BRASS = "#C9972B";
const MUTED = "#8A93A6";
const SEAM_PCT = 40; // left (ink) panel width, %

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
    links: [
      { rel: "preconnect", href: "https://fonts.googleapis.com" },
      { rel: "preconnect", href: "https://fonts.gstatic.com", crossOrigin: "anonymous" },
      {
        rel: "stylesheet",
        href: "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=JetBrains+Mono:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap",
      },
    ],
  }),
  component: LoginPage,
});

const displayFont = "'Space Grotesk', system-ui, sans-serif";
const monoFont = "'JetBrains Mono', 'Courier New', monospace";
const sansFont = "'Inter', system-ui, sans-serif";

function useClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return now;
}

function LoginPage() {
  const { login, isAuthenticated, ready, loginType } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [userType, setUserType] = useState("employee");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const now = useClock();

  useEffect(() => {
    if (ready && isAuthenticated) {
      navigate({ to: "/dashboard", replace: true });
    }
  }, [ready, isAuthenticated, navigate, loginType]);

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

  const timeStr = now.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: true,
  });
  const dateStr = now.toLocaleDateString(undefined, {
    weekday: "long",
    day: "numeric",
    month: "long",
  });

  const fieldSx = {
    "& .MuiOutlinedInput-root": {
      borderRadius: "10px",
      backgroundColor: "#ffffff",
      fontFamily: sansFont,
      "& fieldset": { borderColor: "rgba(18,20,31,0.14)" },
      "&:hover fieldset": { borderColor: "rgba(18,20,31,0.3)" },
      "&.Mui-focused fieldset": { borderColor: BRASS, borderWidth: "1.5px" },
    },
    "& .MuiInputLabel-root": { color: MUTED, fontFamily: sansFont, fontWeight: 500 },
    "& .MuiInputLabel-root.Mui-focused": { color: "#8a6d1f" },
  };

  return (
    <Box
      sx={{
        minHeight: "100dvh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        px: { xs: 2, sm: 3 },
        py: { xs: 4, sm: 6 },
        backgroundColor: PAGE_BG,
        backgroundImage:
          "radial-gradient(circle at 15% 10%, rgba(201,151,43,0.08), transparent 40%), radial-gradient(circle at 85% 90%, rgba(18,20,31,0.05), transparent 45%)",
      }}
    >
      <Box sx={{ width: "100%", maxWidth: 900 }}>
        <Box
          sx={{
            position: "relative",
            display: "flex",
            flexDirection: { xs: "column", sm: "row" },
            width: "100%",
          }}
        >
          {/* Stub — ink panel with live clock */}
          <Box
            sx={{
              flexBasis: { sm: `${SEAM_PCT}%` },
              flexShrink: 0,
              backgroundColor: INK,
              color: PAPER,
              borderRadius: { xs: "20px 20px 0 0", sm: "20px 0 0 20px" },
              boxShadow: "0 20px 44px rgba(18,20,31,0.28)",
              p: { xs: 3.5, sm: 4.5 },
              display: "flex",
              flexDirection: "column",
              justifyContent: "space-between",
              minHeight: { xs: 200, sm: 420 },
            }}
          >
            <Box>
              <Typography
                sx={{
                  fontFamily: displayFont,
                  fontWeight: 700,
                  fontSize: "1.35rem",
                  letterSpacing: "-0.01em",
                }}
              >
                AttendPro
              </Typography>
              <Typography sx={{ fontFamily: sansFont, color: "rgba(246,244,239,0.5)", fontSize: "0.8rem", mt: 0.25 }}>
                Attendance & leave management
              </Typography>
            </Box>

            <Box sx={{ my: { xs: 2, sm: 0 } }}>
              <Typography
                sx={{
                  fontFamily: monoFont,
                  fontVariantNumeric: "tabular-nums",
                  fontWeight: 600,
                  fontSize: { xs: "2.3rem", sm: "2.9rem" },
                  lineHeight: 1,
                  color: PAPER,
                }}
              >
                {timeStr}
              </Typography>
              <Typography sx={{ fontFamily: monoFont, color: BRASS, fontWeight: 500, fontSize: "0.85rem", mt: 1, letterSpacing: "0.01em" }}>
                {dateStr}
              </Typography>
            </Box>

            <Typography
              sx={{
                fontFamily: sansFont,
                fontStyle: "italic",
                fontWeight: 400,
                color: "rgba(246,244,239,0.55)",
                fontSize: "0.92rem",
                display: { xs: "none", sm: "block" },
              }}
            >
              Every minute, accounted for.
            </Typography>
          </Box>

          {/* Perforated seam — desktop only */}
          <Box
            sx={{
              display: { xs: "none", sm: "block" },
              position: "relative",
              width: 0,
              borderLeft: "2px dashed rgba(18,20,31,0.18)",
              "&::before": {
                content: '""',
                position: "absolute",
                top: -12,
                left: -12,
                width: 24,
                height: 24,
                borderRadius: "50%",
                backgroundColor: PAGE_BG,
              },
              "&::after": {
                content: '""',
                position: "absolute",
                bottom: -12,
                left: -12,
                width: 24,
                height: 24,
                borderRadius: "50%",
                backgroundColor: PAGE_BG,
              },
            }}
          />

          {/* Ticket body — form */}
          <Box
            component="form"
            onSubmit={handleSubmit}
            sx={{
              flex: 1,
              backgroundColor: PAPER,
              borderRadius: { xs: "0 0 20px 20px", sm: "0 20px 20px 0" },
              boxShadow: "0 20px 44px rgba(18,20,31,0.1)",
              p: { xs: 3.5, sm: 5 },
              display: "flex",
              flexDirection: "column",
              gap: 2.25,
            }}
          >
            <Box>
              <Typography sx={{ fontFamily: displayFont, fontWeight: 700, fontSize: "1.7rem", color: INK, letterSpacing: "-0.015em" }}>
                Sign in
              </Typography>
              <Typography sx={{ fontFamily: sansFont, color: MUTED, fontSize: "0.92rem", mt: 0.5 }}>
                Choose your account type and enter your company credentials.
              </Typography>
            </Box>

            {/* User type — underline tabs, not a pill toggle */}
            <Box sx={{ display: "flex", gap: 3, borderBottom: "1px solid rgba(18,20,31,0.1)" }}>
              {[
                { value: "employee", label: "Employee" },
                { value: "systemadmin", label: "System admin" },
              ].map((opt) => {
                const active = userType === opt.value;
                return (
                  <Box
                    key={opt.value}
                    component="button"
                    type="button"
                    onClick={() => setUserType(opt.value)}
                    sx={{
                      background: "none",
                      border: "none",
                      cursor: "pointer",
                      fontFamily: sansFont,
                      fontWeight: 600,
                      fontSize: "0.92rem",
                      color: active ? INK : MUTED,
                      pb: 1.25,
                      borderBottom: active ? `2px solid ${BRASS}` : "2px solid transparent",
                      mb: "-1px",
                      transition: "color 150ms ease",
                    }}
                  >
                    {opt.label}
                  </Box>
                );
              })}
            </Box>

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
              sx={fieldSx}
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
                      sx={{ minWidth: "auto", textTransform: "none", color: MUTED, fontSize: "0.75rem", fontWeight: 600 }}
                    >
                      {showPassword ? "Hide" : "Show"}
                    </Button>
                  </InputAdornment>
                ),
              }}
              sx={fieldSx}
            />

            {error && (
              <Box
                sx={{
                  py: 1.1,
                  px: 1.5,
                  borderRadius: "8px",
                  borderLeft: "3px solid #b91c1c",
                  backgroundColor: "rgba(185,28,28,0.06)",
                  color: "#8f1d1d",
                  fontFamily: sansFont,
                  fontSize: "0.86rem",
                  fontWeight: 500,
                }}
              >
                {error}
              </Box>
            )}

            <Button
              type="submit"
              variant="contained"
              fullWidth
              disabled={submitting}
              disableElevation
              sx={{
                py: 1.4,
                mt: 0.5,
                borderRadius: "10px",
                backgroundColor: INK,
                color: PAPER,
                textTransform: "none",
                fontFamily: sansFont,
                fontWeight: 700,
                fontSize: "1rem",
                "&:hover": { backgroundColor: "#1e2136" },
                "&.Mui-disabled": { backgroundColor: "rgba(18,20,31,0.35)", color: "rgba(246,244,239,0.8)" },
              }}
            >
              {submitting ? "Signing in…" : "Sign in"}
            </Button>

            <Typography sx={{ fontFamily: sansFont, color: MUTED, fontSize: "0.8rem", textAlign: "center", mt: 0.5 }}>
              Trouble signing in? Contact your HR administrator.
            </Typography>
          </Box>
        </Box>
      </Box>
    </Box>
  );
}