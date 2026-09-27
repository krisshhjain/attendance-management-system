import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../../lib/api.js";
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Typography,
  CircularProgress,
  Alert,
  Box,
} from "@mui/material";

export function ShiftAssignmentDialog({ open, employee, onClose, onSuccess }) {
  const [selectedShiftId, setSelectedShiftId] = useState("");
  const [isAssigning, setIsAssigning] = useState(false);
  const [error, setError] = useState(null);

  // Fetch available shifts
  const { data: shiftsResponse, isLoading: shiftsLoading } = useQuery({
    queryKey: ["shifts-admin"],
    queryFn: () => apiRequest("/attendance/admin/shift/all/"),
    enabled: open,
  });

  // Reset form when dialog opens/closes
  useEffect(() => {
    if (open && employee) {
      setSelectedShiftId(employee.shift ? employee.shift.id.toString() : "");
      setError(null);
    }
  }, [open, employee]);

  const handleAssign = async () => {
    if (!employee) return;
    
    setIsAssigning(true);
    setError(null);
    
    try {
      const shiftId = selectedShiftId === "" ? null : parseInt(selectedShiftId);
      
      await apiRequest("/attendance/admin/shift/assign/", {
        method: "POST",
        body: {
          employee_email: employee.email,
          shift_id: shiftId,
        },
      });
      
      onSuccess?.();
    } catch (err) {
      setError(err.response?.data?.error || "Failed to assign shift");
    } finally {
      setIsAssigning(false);
    }
  };

  if (!employee) return null;

  // Filter shifts to only show those matching employee's employment type
  const allShifts = shiftsResponse?.shifts || [];
  const shifts = allShifts.filter(shift => 
    shift.employment_type === employee.employment_type
  );
  const displayName = [employee.first_name, employee.last_name].filter(Boolean).join(" ") || employee.email;

  return (
    <Dialog
      open={open}
      onClose={isAssigning ? undefined : onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{ sx: { borderRadius: "16px", p: 1 } }}
    >
      <DialogTitle sx={{ pb: 1 }}>
        <Typography variant="h6" fontWeight={600}>
          Assign Shift to {displayName}
        </Typography>
      </DialogTitle>
      
      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}
        
        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Assign or change the shift for this employee. Leave empty to remove the current shift assignment.
        </Typography>

        {employee.shift && (
          <Box sx={{ mb: 2, p: 2, bgcolor: "grey.50", borderRadius: 1 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
              Current Shift:
            </Typography>
            <Typography variant="body2" fontWeight={600}>
              {employee.shift.code} - {employee.shift.name}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {employee.shift.start_time} - {employee.shift.end_time}
            </Typography>
          </Box>
        )}

        <FormControl fullWidth disabled={isAssigning || shiftsLoading}>
          <InputLabel>New Shift</InputLabel>
          <Select
            value={selectedShiftId}
            onChange={(e) => setSelectedShiftId(e.target.value)}
            label="New Shift"
          >
            <MenuItem value="">
              <em>No Shift (Remove Assignment)</em>
            </MenuItem>
            {shifts.map((shift) => (
              <MenuItem key={shift.id} value={shift.id.toString()}>
                <Box>
                  <Typography variant="body2" fontWeight={600}>
                    {shift.code} - {shift.name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {shift.start_time} - {shift.end_time}
                  </Typography>
                </Box>
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        {shiftsLoading && (
          <Box sx={{ display: "flex", justifyContent: "center", mt: 2 }}>
            <CircularProgress size={24} />
          </Box>
        )}
      </DialogContent>
      
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button 
          onClick={onClose} 
          disabled={isAssigning}
          sx={{ textTransform: "none", fontWeight: 600 }}
        >
          Cancel
        </Button>
        <Button
          variant="contained"
          onClick={handleAssign}
          disabled={isAssigning || shiftsLoading}
          sx={{ textTransform: "none", fontWeight: 600, borderRadius: "8px" }}
        >
          {isAssigning ? (
            <CircularProgress size={22} color="inherit" />
          ) : (
            "Assign Shift"
          )}
        </Button>
      </DialogActions>
    </Dialog>
  );
}