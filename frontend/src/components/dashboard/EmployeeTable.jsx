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
import CameraAltOutlinedIcon from "@mui/icons-material/CameraAltOutlined";
import FaceIcon from "@mui/icons-material/Face";
import { AddEmployeeDialog } from "./AddEmployeeDialog.jsx";
import { EditEmployeeDialog } from "./EditEmployeeDialog.jsx";
import { ChangePasswordDialog } from "./ChangePasswordDialog.jsx";
import WebcamCapture from "../WebcamCapture.jsx";
import VpnKeyOutlinedIcon from "@mui/icons-material/VpnKeyOutlined";
import { TextField, MenuItem, Select, FormControl, InputLabel, InputAdornment } from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";

export function EmployeeTable() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editEmployee, setEditEmployee] = useState(null);
  const [deleteEmployee, setDeleteEmployee] = useState(null);
  const [passwordEmployee, setPasswordEmployee] = useState(null);
  const [enrollEmployee, setEnrollEmployee] = useState(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [enrollLoading, setEnrollLoading] = useState(false);
  const [enrollError, setEnrollError] = useState(null);
  const [enrollSuccess, setEnrollSuccess] = useState(false);
  
  const [searchQuery, setSearchQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");

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

  const handleEnrollFace = async (images) => {
    if (!enrollEmployee) return;
    setEnrollLoading(true);
    setEnrollError(null);
    setEnrollSuccess(false);
    
    try {
      const formData = new FormData();
      images.forEach((img, index) => {
        // Convert base64 to blob
        const split = img.split(',');
        const byteString = atob(split[1]);
        const mimeString = split[0].split(':')[1].split(';')[0];
        const ab = new ArrayBuffer(byteString.length);
        const ia = new Uint8Array(ab);
        for (let i = 0; i < byteString.length; i++) {
          ia[i] = byteString.charCodeAt(i);
        }
        const blob = new Blob([ab], { type: mimeString });
        formData.append("images", blob, `face_${index}.jpg`);
      });

      const token = localStorage.getItem("access_token");
      const res = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api'}/admin/employees/${enrollEmployee.id}/enroll-face/`, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`
        },
        body: formData,
      });
      
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to enroll face");
      
      setEnrollSuccess(true);
      refetch();
      
      // Close dialog after showing success for 2 seconds
      setTimeout(() => {
        setEnrollEmployee(null);
        setEnrollSuccess(false);
      }, 2000);
    } catch (err) {
      setEnrollError(err.message);
    } finally {
      setEnrollLoading(false);
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

  const filteredEmployees = employees?.filter((emp) => {
    const matchesSearch = 
      getDisplayName(emp).toLowerCase().includes(searchQuery.toLowerCase()) || 
      emp.email.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesType = typeFilter === "ALL" || emp.employment_type === typeFilter;
    
    let matchesStatus = true;
    if (statusFilter === "ACTIVE") matchesStatus = emp.is_active;
    if (statusFilter === "INACTIVE") matchesStatus = !emp.is_active;

    return matchesSearch && matchesType && matchesStatus;
  });

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

      {/* Filters */}
      <Box sx={{ p: 2, display: "flex", gap: 2, flexWrap: "wrap", borderBottom: "1px solid", borderColor: "divider", bgcolor: "rgba(0,0,0,0.01)" }}>
        <TextField
          size="small"
          placeholder="Search employees..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          InputProps={{
            startAdornment: <InputAdornment position="start"><SearchIcon fontSize="small" /></InputAdornment>,
            sx: { borderRadius: "8px", bgcolor: "white" }
          }}
          sx={{ minWidth: 250, flexGrow: 1 }}
        />
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <Select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            displayEmpty
            sx={{ borderRadius: "8px", bgcolor: "white" }}
          >
            <MenuItem value="ALL">All Types</MenuItem>
            <MenuItem value="PERMANENT">Permanent</MenuItem>
            <MenuItem value="CONTRACT">Contract</MenuItem>
            <MenuItem value="INTERN">Intern</MenuItem>
          </Select>
        </FormControl>
        <FormControl size="small" sx={{ minWidth: 150 }}>
          <Select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            displayEmpty
            sx={{ borderRadius: "8px", bgcolor: "white" }}
          >
            <MenuItem value="ALL">All Status</MenuItem>
            <MenuItem value="ACTIVE">Active</MenuItem>
            <MenuItem value="INACTIVE">Inactive</MenuItem>
          </Select>
        </FormControl>
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
      ) : !filteredEmployees || filteredEmployees.length === 0 ? (
        <Box sx={{ p: 4, textAlign: "center" }}>
          <Typography color="text.secondary">No employees found matching the filters.</Typography>
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
                <TableCell sx={{ fontWeight: 600, color: "text.secondary", fontSize: "0.75rem", textTransform: "uppercase" }}>Biometrics</TableCell>
                <TableCell sx={{ fontWeight: 600, color: "text.secondary", fontSize: "0.75rem", textTransform: "uppercase" }} align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredEmployees.map((emp) => {
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
                    <TableCell>
                      <Chip
                        label={emp.has_face_enrolled ? "Face Enrolled" : "Not Enrolled"}
                        size="small"
                        sx={{
                          fontWeight: 600,
                          borderRadius: "6px",
                          fontSize: "0.7rem",
                          height: 24,
                          bgcolor: emp.has_face_enrolled ? "rgba(33, 150, 243, 0.1)" : "rgba(158, 158, 158, 0.1)",
                          color: emp.has_face_enrolled ? "#2196f3" : "#9e9e9e",
                        }}
                      />
                    </TableCell>
                    <TableCell align="right">
                      <Box sx={{ display: "flex", justifyContent: "flex-end", gap: 0.5 }}>
                        <Tooltip title={emp.has_face_enrolled ? "Re-enroll Face" : "Enroll Face"}>
                          <IconButton
                            size="small"
                            onClick={() => {
                              setEnrollEmployee(emp);
                              setEnrollSuccess(false);
                              setEnrollError(null);
                            }}
                            sx={{ color: emp.has_face_enrolled ? "success.main" : "text.secondary", "&:hover": { color: "success.dark", bgcolor: "rgba(46,125,50,0.06)" } }}
                          >
                            {emp.has_face_enrolled ? <FaceIcon fontSize="small" /> : <CameraAltOutlinedIcon fontSize="small" />}
                          </IconButton>
                        </Tooltip>
                        <Tooltip title="Reset Password">
                          <IconButton
                            size="small"
                            onClick={() => setPasswordEmployee(emp)}
                            sx={{ color: "text.secondary", "&:hover": { color: "warning.main", bgcolor: "rgba(237,108,2,0.06)" } }}
                          >
                            <VpnKeyOutlinedIcon fontSize="small" />
                          </IconButton>
                        </Tooltip>
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

      {/* Change Password Dialog */}
      <ChangePasswordDialog
        open={Boolean(passwordEmployee)}
        employee={passwordEmployee}
        onClose={() => setPasswordEmployee(null)}
        onSuccess={() => { setPasswordEmployee(null); }}
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

      {/* Face Enrollment Dialog */}
      <Dialog
        open={Boolean(enrollEmployee)}
        onClose={enrollLoading ? undefined : () => setEnrollEmployee(null)}
        maxWidth="md"
        fullWidth
        PaperProps={{ sx: { borderRadius: "16px", p: 1 } }}
      >
        <DialogTitle sx={{ pb: 1 }}>
          <Typography variant="h6" fontWeight={600}>Enroll Face for {enrollEmployee ? getDisplayName(enrollEmployee) : ""}</Typography>
        </DialogTitle>
        <DialogContent>
          {enrollError && (
            <Box sx={{ mb: 2, p: 2, bgcolor: "error.light", color: "error.contrastText", borderRadius: 1 }}>
              <Typography variant="body2">{enrollError}</Typography>
            </Box>
          )}
          {enrollSuccess && (
            <Box sx={{ mb: 2, p: 2, bgcolor: "success.light", color: "success.contrastText", borderRadius: 1 }}>
              <Typography variant="body2">Successfully enrolled! Closing...</Typography>
            </Box>
          )}
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            Please ensure the employee is facing the camera directly in good lighting. The system will automatically take 3 photos.
          </Typography>
          <Box sx={{ display: "flex", justifyContent: "center" }}>
            {enrollEmployee && (
              <WebcamCapture 
                mode="burst"
                onCapture={handleEnrollFace}
                onCancel={() => setEnrollEmployee(null)}
                isLoading={enrollLoading}
              />
            )}
          </Box>
        </DialogContent>
      </Dialog>
    </Paper>
  );
}
