import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { RequireAuth } from "../components/RequireAuth.jsx";
import { apiRequest } from "../lib/api.js";
import { 
  Box, 
  Typography, 
  Paper, 
  TextField, 
  Button, 
  Alert,
  CircularProgress,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions
} from "@mui/material";
import LockOutlinedIcon from "@mui/icons-material/LockOutlined";

export const Route = createFileRoute("/settings")({
  component: Settings,
});

function ChangePasswordDialog({ open, onClose }) {
  const [formData, setFormData] = useState({
    current_password: "",
    new_password: "",
    confirm_password: "",
  });
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const validatePassword = (password) => {
    if (password.length < 8) return "Password must be at least 8 characters long.";
    if (!/[A-Z]/.test(password)) return "Password must contain at least 1 capital letter.";
    if (!/[a-z]/.test(password)) return "Password must contain at least 1 lowercase letter.";
    if (!/[!@#$%^&*(),.?":{}|<>]/.test(password)) return "Password must contain at least 1 symbol.";
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccess(false);

    if (formData.new_password !== formData.confirm_password) {
      setError("New passwords do not match.");
      return;
    }

    const validationError = validatePassword(formData.new_password);
    if (validationError) {
      setError(validationError);
      return;
    }

    setLoading(true);
    try {
      await apiRequest("/auth/change-password/", {
        method: "POST",
        body: {
          current_password: formData.current_password,
          new_password: formData.new_password,
        },
      });
      setSuccess(true);
      setFormData({
        current_password: "",
        new_password: "",
        confirm_password: "",
      });
      setTimeout(() => {
        onClose();
        setSuccess(false);
      }, 1500);
    } catch (err) {
      setError(err.message || "Failed to change password.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onClose={!loading ? onClose : undefined} maxWidth="sm" fullWidth PaperProps={{ sx: { borderRadius: "16px", p: 1 } }}>
      <DialogTitle sx={{ pb: 1 }}>
        <Typography variant="h6" fontWeight={600} letterSpacing="-0.5px">
          Change Password
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          Please enter your current password and choose a new secure password.
        </Typography>
      </DialogTitle>
      
      <form onSubmit={handleSubmit}>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2.5, py: 2 }}>
          {error && <Alert severity="error" sx={{ borderRadius: "8px" }}>{error}</Alert>}
          {success && <Alert severity="success" sx={{ borderRadius: "8px" }}>Password successfully changed.</Alert>}
          
          <TextField
            required
            fullWidth
            label="Current Password"
            name="current_password"
            type="password"
            value={formData.current_password}
            onChange={handleChange}
            size="small"
            autoFocus
          />
          
          <TextField
            required
            fullWidth
            label="New Password"
            name="new_password"
            type="password"
            value={formData.new_password}
            onChange={handleChange}
            size="small"
            helperText="Min 8 chars, 1 capital, 1 lowercase, 1 symbol"
          />
          
          <TextField
            required
            fullWidth
            label="Confirm New Password"
            name="confirm_password"
            type="password"
            value={formData.confirm_password}
            onChange={handleChange}
            size="small"
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2, pt: 1 }}>
          <Button onClick={onClose} disabled={loading} sx={{ textTransform: "none", fontWeight: 600 }}>
            Cancel
          </Button>
          <Button 
            type="submit" 
            variant="contained" 
            disabled={loading}
            sx={{ textTransform: "none", fontWeight: 600, borderRadius: "8px", minWidth: 100 }}
          >
            {loading ? <CircularProgress size={24} color="inherit" /> : "Update"}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

function Settings() {
  const [isPasswordDialogOpen, setPasswordDialogOpen] = useState(false);

  return (
    <RequireAuth>
      <Box sx={{ display: "flex", flexDirection: "column", gap: 3, maxWidth: 600 }}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 700, letterSpacing: "-0.5px" }}>
            Settings
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Update your account settings and preferences.
          </Typography>
        </Box>

        <Paper elevation={0} sx={{ p: 3, borderRadius: 3, border: "1px solid", borderColor: "divider" }}>
          <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
            Security
          </Typography>
          
          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", p: 2, borderRadius: 2, border: "1px solid", borderColor: "divider", bgcolor: "background.default" }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
              <Box sx={{ display: "flex", alignItems: "center", justifyContent: "center", width: 40, height: 40, borderRadius: 2, bgcolor: "primary.lighter", color: "primary.main" }}>
                <LockOutlinedIcon fontSize="small" />
              </Box>
              <Box>
                <Typography variant="body2" fontWeight={600}>
                  Password
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Last changed recently
                </Typography>
              </Box>
            </Box>
            <Button 
              variant="outlined" 
              size="small"
              onClick={() => setPasswordDialogOpen(true)}
              sx={{ textTransform: "none", fontWeight: 600, borderRadius: 2 }}
            >
              Change
            </Button>
          </Box>
        </Paper>
      </Box>

      {isPasswordDialogOpen && (
        <ChangePasswordDialog open={isPasswordDialogOpen} onClose={() => setPasswordDialogOpen(false)} />
      )}
    </RequireAuth>
  );
}
