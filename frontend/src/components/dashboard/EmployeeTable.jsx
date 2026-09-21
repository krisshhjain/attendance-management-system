import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../../lib/api.js";
import {
  Box,
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Avatar,
  CircularProgress,
  Button,
  IconButton,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import { AddEmployeeDialog } from "./AddEmployeeDialog.jsx";
import { EditEmployeeDialog } from "./EditEmployeeDialog.jsx";

export function EmployeeTable() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editEmployee, setEditEmployee] = useState(null);
  const [deleteEmployee, setDeleteEmployee] = useState(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const { data: employees, isLoading, isError, refetch } = useQuery({
    queryKey: ["employees"],
    queryFn: () => apiRequest("/admin/employees/list/"),
  });

  const handleDeleteConfirm = async () => {
    if (!deleteEmployee) return;
    setDeleteLoading(true);
    try {
      await apiRequest(`/admin/employees/${deleteEmployee.id}/`, { method: "DELETE" });
      setDeleteEmployee(null);
      refetch();
    } catch (err) {
      // silently close and let refetch show current state
      setDeleteEmployee(null);
    } finally {
      setDeleteLoading(false);
    }
  };

  const getTypeColor = (type) => {
    switch (type) {
      case "PERMANENT": return "success";
      case "CONTRACT": return "warning";
      case "INTERN": return "info";
      default: return "default";
    }
  };

  const getDisplayName = (emp) => {
    const full = [emp.first_name, emp.last_name].filter(Boolean).join(" ");
    return full || emp.email.split("@")[0];
  };

  return (
    <Paper
      elevation={0}
      sx={{
        borderRadius: "16px",
        border: "1px solid",
        borderColor: "divider",
        bgcolor: "white",
        boxShadow: "0px 2px 4px rgba(0, 0, 0, 0.02)",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <Box sx={{ p: 3, display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid", borderColor: "divider", flexWrap: "wrap", gap: 2 }}>
        <Box>
          <Typography variant="h6" sx={{ fontWeight: 600, letterSpacing: "-0.5px" }}>
            Employee Details
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Manage your team members and their employment status.
          </Typography>
        </Box>
        <Button
          variant="contained"
          color="primary"
          startIcon={<AddIcon />}
          onClick={() => setDialogOpen(true)}
          sx={{ borderRadius: "8px", textTransform: "none", fontWeight: 600 }}
        >
          Add Employee
        </Button>
      </Box>

      {isLoading ? (
        <Box sx={{ p: 4, display: "flex", justifyContent: "center" }}>
          <CircularProgress size={32} />
        </Box>
      ) : isError ? (
        <Box sx={{ p: 4, textAlign: "center" }}>
          <Typography color="error">Unable to load employees. Try again.</Typography>
          <Button variant="outlined" size="small" onClick={() => refetch()} sx={{ mt: 2 }}>
            Retry
          </Button>
        </Box>
      ) : !employees || employees.length === 0 ? (
        <Box sx={{ p: 4, textAlign: "center" }}>
          <Typography color="text.secondary">No employees found.</Typography>
        </Box>
      ) : (
        <TableContainer sx={{ overflowX: "auto" }}>
          <Table sx={{ minWidth: 650 }}>
            <TableHead sx={{ bgcolor: "rgba(0,0,0,0.02)" }}>
              <TableRow>
                <TableCell sx={{ fontWeight: 600, color: "text.secondary", fontSize: "0.75rem", textTransform: "uppercase" }}>Employee</TableCell>
                <TableCell sx={{ fontWeight: 600, color: "text.secondary", fontSize: "0.75rem", textTransform: "uppercase" }}>Department</TableCell>
                <TableCell sx={{ fontWeight: 600, color: "text.secondary", fontSize: "0.75rem", textTransform: "uppercase" }}>Type</TableCell>
                <TableCell sx={{ fontWeight: 600, color: "text.secondary", fontSize: "0.75rem", textTransform: "uppercase" }}>Sec</TableCell>
                <TableCell sx={{ fontWeight: 600, color: "text.secondary", fontSize: "0.75rem", textTransform: "uppercase" }}>Sub</TableCell>
                <TableCell sx={{ fontWeight: 600, color: "text.secondary", fontSize: "0.75rem", textTransform: "uppercase" }}>Date Joined</TableCell>
                <TableCell sx={{ fontWeight: 600, color: "text.secondary", fontSize: "0.75rem", textTransform: "uppercase" }}>Status</TableCell>
                <TableCell sx={{ fontWeight: 600, color: "text.secondary", fontSize: "0.75rem", textTransform: "uppercase" }} align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {employees.map((emp) => {
                const initials = getDisplayName(emp).slice(0, 2).toUpperCase();
                return (
                  <TableRow
                    key={emp.id}
                    sx={{ "&:last-child td, &:last-child th": { border: 0 }, "&:hover": { bgcolor: "rgba(0,0,0,0.01)" } }}
                  >
                    <TableCell>
                      <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
                        <Avatar sx={{ width: 32, height: 32, bgcolor: "action.selected", color: "text.primary", fontSize: "0.875rem", fontWeight: "bold" }}>
                          {initials}
                        </Avatar>
                        <Box>
                          <Typography variant="body2" fontWeight={600}>
                            {getDisplayName(emp)}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {emp.email}
                          </Typography>
                        </Box>
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" fontWeight={500} color="text.primary">
                        {emp.department || "-"}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={emp.employment_type || "Unknown"}
                        size="small"
                        color={getTypeColor(emp.employment_type)}
                        sx={{ fontWeight: 600, borderRadius: "6px", fontSize: "0.7rem", height: 24 }}
                      />
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {emp.section || "-"}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {emp.subsection || "-"}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" color="text.secondary">
                        {emp.date_joined || "-"}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={emp.is_active ? "Active" : "Inactive"}
                        size="small"
                        sx={{
                          fontWeight: 600,
                          borderRadius: "6px",
                          fontSize: "0.7rem",
                          height: 24,
                          bgcolor: emp.is_active ? "rgba(76, 175, 80, 0.1)" : "rgba(158, 158, 158, 0.1)",
                          color: emp.is_active ? "#4caf50" : "#9e9e9e",
                        }}
                      />
                    </TableCell>
                    <TableCell align="right">
                      <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 0.5 }}>
                        <Tooltip title="Edit Employee">
                          <IconButton
                            size="small"
                            onClick={() => setEditEmployee(emp)}
                            sx={{ color: "text.secondary", "&:hover": { color: "primary.main", bgcolor: "rgba(125,37,169,0.06)" } }}
                          >
                            <EditOutlinedIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Delete Employee">
                          <IconButton
                            size="small"
                            onClick={() => setDeleteEmployee(emp)}
                            sx={{ color: "text.secondary", "&:hover": { color: "error.main", bgcolor: "rgba(211,47,47,0.06)" } }}
                          >
                            <DeleteOutlineIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
                      </Box>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {/* Add Dialog */}
      <AddEmployeeDialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        onSuccess={() => { setDialogOpen(false); refetch(); }}
      />

      {/* Edit Dialog */}
      <EditEmployeeDialog
        open={Boolean(editEmployee)}
        employee={editEmployee}
        onClose={() => setEditEmployee(null)}
        onSuccess={() => { setEditEmployee(null); refetch(); }}
      />

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={Boolean(deleteEmployee)}
        onClose={deleteLoading ? undefined : () => setDeleteEmployee(null)}
        maxWidth="xs"
        fullWidth
        PaperProps={{ sx: { borderRadius: "16px", p: 1 } }}
      >
        <DialogTitle sx={{ pb: 1 }}>
          <Typography variant="h6" fontWeight={600}>Delete Employee?</Typography>
        </DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary">
            This will permanently delete <strong>{deleteEmployee ? [deleteEmployee.first_name, deleteEmployee.last_name].filter(Boolean).join(" ") || deleteEmployee.email : ""}</strong> and their account. This action cannot be undone.
          </Typography>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setDeleteEmployee(null)} disabled={deleteLoading} sx={{ textTransform: "none", fontWeight: 600 }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            color="error"
            disabled={deleteLoading}
            onClick={handleDeleteConfirm}
            sx={{ textTransform: "none", fontWeight: 600, borderRadius: "8px" }}
          >
            {deleteLoading ? <CircularProgress size={22} color="inherit" /> : "Delete"}
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
}
