import { useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Typography,
  CircularProgress,
  Alert,
} from "@mui/material";
import { apiRequest } from "../../lib/api";

export function ChangePasswordDialog({ open, employee, onClose, onSuccess }) {
  const [newPassword, setNewPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!newPassword || newPassword.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await apiRequest(`/admin/employees/${employee.id}/change-password/`, {
        method: "POST",
        body: { new_password: newPassword },
      });
      onSuccess();
    } catch (err) {
      setError(err.message || "Failed to reset password");
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setNewPassword("");
    setError(null);
    onClose();
  };

  const displayName = employee ? [employee.first_name, employee.last_name].filter(Boolean).join(" ") || employee.email : "";

  return (
    <Dialog open={open} onClose={loading ? undefined : handleClose} maxWidth="xs" fullWidth PaperProps={{ sx: { borderRadius: "16px", p: 1 } }}>
      <DialogTitle sx={{ pb: 1 }}>
        <Typography variant="h6" fontWeight={600}>
          Reset Password
        </Typography>
      </DialogTitle>
      <form onSubmit={handleSubmit}>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <Typography variant="body2" color="text.secondary">
            Set a new password for <strong>{displayName}</strong>. They will be able to log in with this new password immediately.
          </Typography>
          
          {error && <Alert severity="error" sx={{ borderRadius: "8px" }}>{error}</Alert>}
          
          <TextField
            label="New Password"
            type="password"
            fullWidth
            required
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            disabled={loading}
            size="small"
            helperText="Must be at least 8 characters long."
            InputProps={{ sx: { borderRadius: "8px" } }}
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={handleClose} disabled={loading} sx={{ textTransform: "none", fontWeight: 600 }}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="contained"
            color="primary"
            disabled={loading}
            sx={{ textTransform: "none", fontWeight: 600, borderRadius: "8px" }}
          >
            {loading ? <CircularProgress size={22} color="inherit" /> : "Reset Password"}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
