import { useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Typography,
  Box,
  Alert,
  CircularProgress,
} from "@mui/material";
import LockResetIcon from "@mui/icons-material/LockReset";
import LogoutIcon from "@mui/icons-material/Logout";
import { apiRequest } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";

export function ForcePasswordChangeModal({ open }) {
  const { logout } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (newPassword.length < 8) {
      setError("New password must be at least 8 characters long.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("New passwords do not match.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await apiRequest("/auth/change-password/", {
        method: "POST",
        body: { current_password: currentPassword, new_password: newPassword },
      });
      // After changing password, reload so the fresh /auth/me/ profile is fetched
      window.location.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to change password.");
      setLoading(false);
    }
  };

  return (
    <Dialog
      open={open}
      disableEscapeKeyDown
      maxWidth="xs"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: "16px",
          p: 1,
          boxShadow: "0 20px 40px rgba(0,0,0,0.15)",
        },
      }}
    >
      <DialogTitle sx={{ pb: 1, display: "flex", alignItems: "center", gap: 1.5 }}>
        <Box
          sx={{
            width: 40,
            height: 40,
            borderRadius: "10px",
            bgcolor: "primary.lighter",
            backgroundColor: "rgba(125, 37, 169, 0.1)",
            color: "primary.main",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <LockResetIcon />
        </Box>
        <Box>
          <Typography variant="h6" fontWeight={700} sx={{ letterSpacing: "-0.5px" }}>
            First-Time Password Setup
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Action required to continue
          </Typography>
        </Box>
      </DialogTitle>

      <Box component="form" onSubmit={handleSubmit}>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 1 }}>
          <Typography variant="body2" color="text.secondary">
            Since this is your first time logging in (or your password was recently reset), please choose a new secure password for your account.
          </Typography>

          {error && (
            <Alert severity="error" sx={{ borderRadius: "8px" }}>
              {error}
            </Alert>
          )}

          <TextField
            label="Current (Temporary) Password"
            type="password"
            fullWidth
            required
            size="small"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            disabled={loading}
            InputProps={{ sx: { borderRadius: "8px" } }}
          />
          <TextField
            label="New Password"
            type="password"
            fullWidth
            required
            size="small"
            helperText="Must be at least 8 characters long."
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            disabled={loading}
            InputProps={{ sx: { borderRadius: "8px" } }}
          />
          <TextField
            label="Confirm New Password"
            type="password"
            fullWidth
            required
            size="small"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            disabled={loading}
            InputProps={{ sx: { borderRadius: "8px" } }}
          />
        </DialogContent>

        <DialogActions sx={{ px: 3, pb: 2, pt: 1, display: "flex", justifyContent: "space-between" }}>
          <Button
            onClick={() => logout()}
            disabled={loading}
            startIcon={<LogoutIcon fontSize="small" />}
            sx={{ textTransform: "none", color: "text.secondary" }}
          >
            Sign Out
          </Button>
          <Button
            type="submit"
            variant="contained"
            color="primary"
            disabled={loading}
            sx={{
              textTransform: "none",
              fontWeight: 600,
              borderRadius: "8px",
              px: 3,
            }}
          >
            {loading ? <CircularProgress size={22} color="inherit" /> : "Set Password & Continue"}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
}
