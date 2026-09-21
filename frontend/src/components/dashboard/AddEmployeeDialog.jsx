import { useState } from "react";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  MenuItem,
  Box,
  Typography,
  CircularProgress,
  Alert
} from "@mui/material";
import { apiRequest } from "../../lib/api.js";

const EMPLOYMENT_TYPES = ["PERMANENT", "CONTRACT", "INTERN"];

export function AddEmployeeDialog({ open, onClose, onSuccess }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [formData, setFormData] = useState({
    first_name: "",
    last_name: "",
    email: "",
    password: "",
    department: "",
    section: "",
    subsection: "",
    employment_type: "PERMANENT",
    date_joined: new Date().toISOString().split("T")[0],
  });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await apiRequest("/admin/employees/", {
        method: "POST",
        body: formData,
      });

      setFormData({
        first_name: "",
        last_name: "",
        email: "",
        password: "",
        department: "",
        section: "",
        subsection: "",
        employment_type: "PERMANENT",
        date_joined: new Date().toISOString().split("T")[0],
      });

      onSuccess();
    } catch (err) {
      setError(err.message || "Failed to create employee.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onClose={!loading ? onClose : undefined} maxWidth="sm" fullWidth PaperProps={{ sx: { borderRadius: "16px", p: 1 } }}>
      <DialogTitle sx={{ pb: 1 }}>
        <Typography variant="h6" fontWeight={600} letterSpacing="-0.5px">
          Add New Employee
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          Create a new employee account and set their employment details.
        </Typography>
      </DialogTitle>

      <form onSubmit={handleSubmit}>
        <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2.5, py: 2 }}>
          {error && <Alert severity="error" sx={{ borderRadius: "8px" }}>{error}</Alert>}

          {/* Name row */}
          <Box sx={{ display: "flex", gap: 2, flexDirection: { xs: "column", sm: "row" } }}>
            <TextField
              fullWidth
              label="First Name"
              name="first_name"
              value={formData.first_name}
              onChange={handleChange}
              size="small"
              placeholder="John"
            />
            <TextField
              fullWidth
              label="Last Name"
              name="last_name"
              value={formData.last_name}
              onChange={handleChange}
              size="small"
              placeholder="Doe"
            />
          </Box>

          {/* Email + Password row */}
          <Box sx={{ display: "flex", gap: 2, flexDirection: { xs: "column", sm: "row" } }}>
            <TextField
              required
              fullWidth
              label="Email Address"
              name="email"
              type="email"
              value={formData.email}
              onChange={handleChange}
              size="small"
              placeholder="employee@company.com"
              autoFocus
            />
            <TextField
              required
              fullWidth
              label="Temporary Password"
              name="password"
              type="text"
              value={formData.password}
              onChange={handleChange}
              size="small"
              placeholder="Min 8 characters"
            />
          </Box>

          {/* Department + Employment type */}
          <Box sx={{ display: "flex", gap: 2, flexDirection: { xs: "column", sm: "row" } }}>
            <TextField
              fullWidth
              label="Department"
              name="department"
              value={formData.department}
              onChange={handleChange}
              size="small"
              placeholder="e.g. Engineering"
            />
            <TextField
              required
              fullWidth
              select
              label="Employment Type"
              name="employment_type"
              value={formData.employment_type}
              onChange={handleChange}
              size="small"
            >
              {EMPLOYMENT_TYPES.map((option) => (
                <MenuItem key={option} value={option}>
                  {option}
                </MenuItem>
              ))}
            </TextField>
          </Box>

          {/* Section + Subsection */}
          <Box sx={{ display: "flex", gap: 2, flexDirection: { xs: "column", sm: "row" } }}>
            <TextField
              fullWidth
              label="Section"
              name="section"
              value={formData.section}
              onChange={handleChange}
              size="small"
              placeholder="e.g. A"
            />
            <TextField
              fullWidth
              label="Subsection"
              name="subsection"
              value={formData.subsection}
              onChange={handleChange}
              size="small"
              placeholder="e.g. A1"
            />
          </Box>

          <TextField
            required
            fullWidth
            label="Date Joined"
            name="date_joined"
            type="date"
            value={formData.date_joined}
            onChange={handleChange}
            size="small"
            InputLabelProps={{ shrink: true }}
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
            {loading ? <CircularProgress size={24} color="inherit" /> : "Create"}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
