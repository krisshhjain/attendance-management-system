import { useState, useEffect } from "react";
import {
  Box,
  Typography,
  Paper,
  Button,
  Chip,
  Alert,
  CircularProgress,
  IconButton,
  TextField,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import SaveIcon from "@mui/icons-material/Save";
import {
  fetchAdminShiftConfiguration,
  configureEmploymentTypeShifts,
} from "../lib/api.js";

export function ShiftConfigurationPanel() {
  const [selectedType, setSelectedType] = useState("PERMANENT");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [configuration, setConfiguration] = useState({
    PERMANENT: [],
    CONTRACT: [],
    INTERN: [],
  });

  // Editing state: array of shift objects being configured for the selected type
  const [editingShifts, setEditingShifts] = useState([]);
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    loadConfiguration();
  }, []);

  const loadConfiguration = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAdminShiftConfiguration();
      setConfiguration(data.configuration || {});
    } catch (err) {
      setError(err.message || "Failed to load shift configuration");
    } finally {
      setLoading(false);
    }
  };

  const handleTypeChange = (type) => {
    if (hasChanges) {
      if (!window.confirm("You have unsaved changes. Discard them?")) {
        return;
      }
    }
    setSelectedType(type);
    setEditingShifts([]);
    setHasChanges(false);
    setError(null);
    setSuccess(null);
  };

  const startEditing = () => {
    const current = configuration[selectedType] || [];
    setEditingShifts(
      current.map((s) => ({
        name: s.name,
        start_time: s.start_time,
        end_time: s.end_time,
      }))
    );
    // Start with at least one empty shift if none exist
    if (current.length === 0) {
      setEditingShifts([{ name: "", code: "", start_time: "09:00", end_time: "17:00" }]);
    }
    setHasChanges(true); // Set to true to trigger editing mode
    setError(null);
    setSuccess(null);
  };

  const addShift = () => {
    setEditingShifts([
      ...editingShifts,
      { name: "", code: "", start_time: "09:00", end_time: "17:00" },
    ]);
    setHasChanges(true);
  };

  const removeShift = (index) => {
    setEditingShifts(editingShifts.filter((_, i) => i !== index));
    setHasChanges(true);
  };

  const updateShift = (index, field, value) => {
    const updated = [...editingShifts];
    updated[index][field] = value;
    setEditingShifts(updated);
    setHasChanges(true);
  };

  const handleSave = async () => {
    setError(null);
    setSuccess(null);

    // Validation
    for (let i = 0; i < editingShifts.length; i++) {
      const shift = editingShifts[i];
      if (!shift.name.trim()) {
        setError(`Shift ${i + 1}: Name is required`);
        return;
      }
      if (!shift.start_time || !shift.end_time) {
        setError(`Shift ${i + 1}: Start time and end time are required`);
        return;
      }
    }

    setLoading(true);
    try {
      const result = await configureEmploymentTypeShifts(
        selectedType,
        editingShifts
      );
      setSuccess(
        `Successfully configured ${editingShifts.length} shift(s) for ${selectedType} employees`
      );
      setEditingShifts([]);
      setHasChanges(false);
      await loadConfiguration();
    } catch (err) {
      setError(err.message || "Failed to save shift configuration");
    } finally {
      setLoading(false);
    }
  };

  const cancelEditing = () => {
    if (
      hasChanges &&
      !window.confirm("Discard unsaved changes?")
    ) {
      return;
    }
    setEditingShifts([]);
    setHasChanges(false);
    setError(null);
    setSuccess(null);
  };

  const currentShifts = configuration[selectedType] || [];
  const isEditing = editingShifts.length > 0 || hasChanges;

  return (
    <Box sx={{ p: 3 }}>
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          mb: 2.5,
          flexWrap: "wrap",
          gap: 1.5,
        }}
      >
        <Box sx={{ display: "flex", gap: 1, alignItems: "center" }}>
          <Typography variant="h6" fontWeight={700} sx={{ mr: 1 }}>
            Configure Shifts by Employment Type:
          </Typography>
          {["PERMANENT", "CONTRACT", "INTERN"].map((type) => (
            <Chip
              key={type}
              label={type}
              clickable
              color={selectedType === type ? "primary" : "default"}
              onClick={() => handleTypeChange(type)}
              sx={{ fontWeight: 700 }}
            />
          ))}
        </Box>
        {!isEditing && (
          <Button
            variant="contained"
            color="primary"
            startIcon={<AddIcon />}
            onClick={startEditing}
            disabled={loading}
            sx={{ borderRadius: 2, textTransform: "none", fontWeight: 600 }}
          >
            Configure Shifts
          </Button>
        )}
      </Box>

      {error && (
        <Alert severity="error" onClose={() => setError(null)} sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      {success && (
        <Alert severity="success" onClose={() => setSuccess(null)} sx={{ mb: 2 }}>
          {success}
        </Alert>
      )}

      {loading && !isEditing ? (
        <Box sx={{ display: "flex", p: 6, justifyContent: "center" }}>
          <CircularProgress size={32} />
        </Box>
      ) : isEditing ? (
        <Paper
          elevation={0}
          sx={{
            border: "1px solid",
            borderColor: "divider",
            borderRadius: 2,
            p: 3,
          }}
        >
          <Box
            sx={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              mb: 2,
            }}
          >
            <Typography variant="subtitle1" fontWeight={600}>
              Configuring shifts for {selectedType} employees
            </Typography>
            <Button
              size="small"
              startIcon={<AddIcon />}
              onClick={addShift}
              sx={{ textTransform: "none" }}
            >
              Add Shift
            </Button>
          </Box>

          {editingShifts.length === 0 ? (
            <Alert severity="info" sx={{ mb: 2 }}>
              Click "Add Shift" to configure shifts for this employment type. You
              can configure 0, 1, or multiple shifts.
            </Alert>
          ) : (
            <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mb: 2 }}>
              {editingShifts.map((shift, index) => (
                <Paper
                  key={index}
                  elevation={0}
                  sx={{
                    border: "1px solid",
                    borderColor: "divider",
                    borderRadius: 1.5,
                    p: 2,
                    bgcolor: "#fafafa",
                  }}
                >
                  <Box sx={{ display: "flex", gap: 2, alignItems: "start" }}>
                    <Typography
                      variant="body2"
                      fontWeight={600}
                      sx={{ mt: 2, minWidth: 60 }}
                    >
                      Shift {index + 1}
                    </Typography>
                    <TextField
                      size="small"
                      label="Shift Name"
                      value={shift.name}
                      onChange={(e) =>
                        updateShift(index, "name", e.target.value)
                      }
                      placeholder="e.g. Morning Shift"
                      sx={{ flexGrow: 1 }}
                      required
                    />
                    <TextField
                      size="small"
                      label="Shift Code"
                      value={shift.code || ""}
                      onChange={(e) =>
                        updateShift(index, "code", e.target.value.toUpperCase())
                      }
                      placeholder="e.g. MORN"
                      sx={{ width: 120 }}
                      helperText="Optional"
                    />
                    <TextField
                      size="small"
                      type="time"
                      label="Start Time"
                      value={shift.start_time}
                      onChange={(e) =>
                        updateShift(index, "start_time", e.target.value)
                      }
                      InputLabelProps={{ shrink: true }}
                      sx={{ width: 140 }}
                      required
                    />
                    <TextField
                      size="small"
                      type="time"
                      label="End Time"
                      value={shift.end_time}
                      onChange={(e) =>
                        updateShift(index, "end_time", e.target.value)
                      }
                      InputLabelProps={{ shrink: true }}
                      sx={{ width: 140 }}
                      required
                    />
                    <IconButton
                      size="small"
                      color="error"
                      onClick={() => removeShift(index)}
                      sx={{ mt: 0.5 }}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Box>
                </Paper>
              ))}
            </Box>
          )}

          <Box sx={{ display: "flex", gap: 1, justifyContent: "flex-end" }}>
            <Button onClick={cancelEditing} disabled={loading}>
              Cancel
            </Button>
            <Button
              variant="contained"
              color="primary"
              startIcon={loading ? <CircularProgress size={16} /> : <SaveIcon />}
              onClick={handleSave}
              disabled={loading || !hasChanges}
            >
              Save Configuration
            </Button>
          </Box>
        </Paper>
      ) : (
        <TableContainer>
          <Table>
            <TableHead
              sx={{ bgcolor: "#f8fafc", borderBottom: "1px solid #f1f5f9" }}
            >
              <TableRow>
                <TableCell
                  sx={{
                    textTransform: "uppercase",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    letterSpacing: 0.5,
                    color: "#64748b",
                    py: 2,
                  }}
                >
                  Shift Name
                </TableCell>
                <TableCell
                  sx={{
                    textTransform: "uppercase",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    letterSpacing: 0.5,
                    color: "#64748b",
                    py: 2,
                  }}
                >
                  Code
                </TableCell>
                <TableCell
                  sx={{
                    textTransform: "uppercase",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    letterSpacing: 0.5,
                    color: "#64748b",
                    py: 2,
                  }}
                >
                  Start Time
                </TableCell>
                <TableCell
                  sx={{
                    textTransform: "uppercase",
                    fontSize: "0.75rem",
                    fontWeight: 700,
                    letterSpacing: 0.5,
                    color: "#64748b",
                    py: 2,
                  }}
                >
                  End Time
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {currentShifts.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} align="center" sx={{ py: 4 }}>
                    <Typography variant="body2" color="text.secondary">
                      No shifts configured for {selectedType} employees.
                    </Typography>
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      display="block"
                      sx={{ mt: 0.5 }}
                    >
                      Click "Configure Shifts" to set up shifts for this employment
                      type.
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                currentShifts.map((shift) => (
                  <TableRow key={shift.id} hover>
                    <TableCell>
                      <Typography variant="body2" fontWeight={600}>
                        {shift.name}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={shift.code}
                        size="small"
                        variant="outlined"
                        sx={{ fontWeight: 600 }}
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">{shift.start_time}</Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">{shift.end_time}</Typography>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}
