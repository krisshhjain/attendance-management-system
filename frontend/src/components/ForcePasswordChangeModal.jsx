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
} from "@mui/material";
import { apiRequest } from "../lib/api.js";
import { useAuth } from "../lib/auth.jsx";

export function ForcePasswordChangeModal({ open }) {
  const { user, loginType, login } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
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
      // After a successful password change, we should refresh the user data
      // or re-login. Re-login is simplest to refresh the token if needed,
      // but simply fetching user again would clear the must_change_password flag.
      // We will just reload the window to let the app refetch everything cleanly.
      window.location.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to change password.");
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} disableEscapeKeyDown>
      <DialogTitle>Update Your Password</DialogTitle>
      <Box component="form" onSubmit={handleSubmit}>
        <DialogContent sx={{ minWidth: 400 }}>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            For security reasons, you must change your password before you can continue using the application.
          </Typography>

          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          <TextField
            label="Current Password"
            type="password"
            fullWidth
            required
            margin="normal"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
          />
          <TextField
            label="New Password"
            type="password"
            fullWidth
            required
            margin="normal"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
          />
          <TextField
            label="Confirm New Password"
            type="password"
            fullWidth
            required
            margin="normal"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 3 }}>
          <Button type="submit" variant="contained" disabled={loading} fullWidth>
            {loading ? "Updating..." : "Update Password"}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
  );
}
