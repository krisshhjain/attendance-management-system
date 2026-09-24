import { useState, useEffect } from "react";
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
  Alert,
  Switch,
  FormControlLabel,
  FormGroup,
  Checkbox,
  Divider,
} from "@mui/material";
import { apiRequest } from "../../lib/api.js";

const EMPLOYMENT_TYPES = ["PERMANENT", "CONTRACT", "INTERN"];

export function EditEmployeeDialog({ open, onClose, onSuccess, employee }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [formData, setFormData] = useState({
    first_name: "",
    last_name: "",
    department: "",
    section: "",
    subsection: "",
    employment_type: "PERMANENT",
    date_joined: "",
    is_active: true,
    app_access: { dashboard: true, attendance: true, leave: true },
  });

  // Populate form when employee prop changes
  useEffect(() => {
    if (employee) {
      setFormData({
        first_name: employee.first_name || "",
        last_name: employee.last_name || "",
        department: employee.department || "",
        section: employee.section || "",
        subsection: employee.subsection || "",
        employment_type: employee.employment_type || "PERMANENT",
        date_joined: employee.date_joined || "",
        is_active: employee.is_active ?? true,
        app_access: employee.app_access || { dashboard: true, attendance: true, leave: true },
      });
      setError(null);
    }
  }, [employee]);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({ ...prev, [name]: type === "checkbox" ? checked : value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await apiRequest(`/admin/employees/${employee.id}/`, {
        method: "PATCH",
        body: formData,
      });
      onSuccess();
    } catch (err) {
      setError(err.message || "Failed to update employee.");
    } finally {
      setLoading(false);
    }
  };

  if (!employee) return null;

  return (
    <Dialog open={open} onClose={!loading ? onClose : undefined} maxWidth="sm" fullWidth PaperProps={{ sx: { borderRadius: "16px", p: 1 } }}>
      <DialogTitle sx={{ pb: 1 }}>
        <Typography variant="h6" fontWeight={600} letterSpacing="-0.5px">
          Edit Employee
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
          {employee.email}
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
            />
            <TextField
              fullWidth
              label="Last Name"
              name="last_name"
              value={formData.last_name}
              onChange={handleChange}
              size="small"
            />
          </Box>

          {/* Department + Type */}
          <Box sx={{ display: "flex", gap: 2, flexDirection: { xs: "column", sm: "row" } }}>
            <TextField
              fullWidth
              label="Department"
              name="department"
              value={formData.department}
              onChange={handleChange}
              size="small"
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
            />
            <TextField
              fullWidth
              label="Subsection"
              name="subsection"
              value={formData.subsection}
              onChange={handleChange}
              size="small"
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

          <FormControlLabel
            control={
              <Switch
                name="is_active"
                checked={formData.is_active}
                onChange={handleChange}
                color="success"
              />
            }
            label={
              <Typography variant="body2" fontWeight={500}>
                {formData.is_active ? "Active" : "Inactive"}
              </Typography>
            }
          />

          <Divider />
          <Box>
            <Typography variant="subtitle2" fontWeight={600}>
              App access
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Choose which areas this employee can use.
            </Typography>
            <FormGroup row sx={{ mt: 0.5, gap: { xs: 0, sm: 1 } }}>
              {[
                ["dashboard", "Dashboard"],
                ["attendance", "Attendance"],
                ["leave", "Leave"],
              ].map(([key, label]) => (
                <FormControlLabel
                  key={key}
                  label={label}
                  control={
                    <Checkbox
                      checked={Boolean(formData.app_access?.[key])}
                      onChange={(event) => setFormData((prev) => ({
                        ...prev,
                        app_access: { ...prev.app_access, [key]: event.target.checked },
                      }))}
                    />
                  }
                />
              ))}
            </FormGroup>
          </Box>
        </DialogContent>

        <DialogActions sx={{ px: 3, pb: 2, pt: 1 }}>
          <Button onClick={onClose} disabled={loading} sx={{ textTransform: "none", fontWeight: 600 }}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={loading}
            sx={{ textTransform: "none", fontWeight: 600, borderRadius: "8px", minWidth: 120 }}
          >
            {loading ? <CircularProgress size={24} color="inherit" /> : "Save Changes"}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}
