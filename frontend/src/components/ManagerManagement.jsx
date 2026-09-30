import React, { useState } from "react";
import {
  Box, Typography, Paper, Button, Dialog, DialogTitle, DialogContent,
  DialogActions, TextField, Table, TableBody, TableCell, TableContainer,
  TableHead, TableRow, Chip, IconButton, Alert, CircularProgress, Autocomplete,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import KeyIcon from "@mui/icons-material/Key";
import { useQuery, useMutation } from "@tanstack/react-query";
import { apiRequest } from "../lib/api.js";
import { useFeedback } from "../feedback/FeedbackProvider.jsx";

const AVAILABLE_SECTIONS = ["A", "B", "C", "D", "E"];
const AVAILABLE_SUBSECTIONS = ["A1", "A2", "B1", "B2", "C1", "C2", "C3", "D1", "D2", "E1"];

export function ManagerManagement() {
  const [createDialog, setCreateDialog] = useState(false);
  const [editDialog, setEditDialog] = useState({ open: false, manager: null });
  const [passwordDialog, setPasswordDialog] = useState({ open: false, manager: null });
  const [deleteDialog, setDeleteDialog] = useState({ open: false, manager: null });
  const { success, notifyError } = useFeedback();

  const { data: managers = [], isLoading, refetch } = useQuery({
    queryKey: ["managers"],
    queryFn: () => apiRequest("/admin/employees/managers/list/"),
  });

  const createMutation = useMutation({
    mutationFn: (data) => apiRequest("/admin/employees/managers/", { method: "POST", body: data }),
    onSuccess: () => { success("Manager created successfully."); setCreateDialog(false); refetch(); },
    onError: (err) => notifyError(err, { title: "Manager creation failed", fallback: "Failed to create manager." }),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }) => apiRequest(`/admin/employees/managers/${id}/`, { method: "PATCH", body: data }),
    onSuccess: () => { success("Manager updated successfully."); setEditDialog({ open: false, manager: null }); refetch(); },
    onError: (err) => notifyError(err, { title: "Manager update failed", fallback: "Failed to update manager." }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id) => apiRequest(`/admin/employees/managers/${id}/`, { method: "DELETE" }),
    onSuccess: () => { success("Manager deleted successfully."); setDeleteDialog({ open: false, manager: null }); refetch(); },
    onError: (err) => notifyError(err, { title: "Manager deletion failed", fallback: "Failed to delete manager." }),
  });

  const passwordMutation = useMutation({
    mutationFn: ({ id, password }) => apiRequest(`/admin/employees/managers/${id}/change-password/`, {
      method: "POST", body: { new_password: password },
    }),
    onSuccess: () => { success("Manager password changed successfully."); setPasswordDialog({ open: false, manager: null }); },
    onError: (err) => notifyError(err, { title: "Password change failed", fallback: "Failed to change manager password." }),
  });

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: "flex", justifyContent: "space-between", mb: 3 }}>
        <Box>
          <Typography variant="h5" fontWeight={700} sx={{ mb: 1 }}>Manager Management</Typography>
          <Typography variant="body2" color="text.secondary">
            Create and manage Manager accounts with scoped access.
          </Typography>
        </Box>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => setCreateDialog(true)}
          sx={{ borderRadius: 2, textTransform: "none", fontWeight: 600 }}>
          Create Manager
        </Button>
      </Box>

      <Paper elevation={0} sx={{ border: "1px solid", borderColor: "divider" }}>
        <TableContainer>
          <Table>
            <TableHead sx={{ bgcolor: "#f8fafc" }}>
              <TableRow>
                <TableCell sx={{ fontWeight: 700 }}>Name</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Email</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Status</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Scope</TableCell>
                <TableCell sx={{ fontWeight: 700 }}>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {isLoading ? (
                <TableRow><TableCell colSpan={5} align="center" sx={{ py: 4 }}>
                  <CircularProgress size={32} />
                </TableCell></TableRow>
              ) : managers.length === 0 ? (
                <TableRow><TableCell colSpan={5} align="center" sx={{ py: 4 }}>
                  <Typography variant="body2" color="text.secondary">No managers found.</Typography>
                </TableCell></TableRow>
              ) : (
                managers.map((manager) => (
                  <TableRow key={manager.id} hover>
                    <TableCell><Typography variant="body2" fontWeight={600}>
                      {manager.first_name} {manager.last_name}
                    </Typography></TableCell>
                    <TableCell><Typography variant="body2">{manager.email}</Typography></TableCell>
                    <TableCell>
                      <Chip label={manager.is_active ? "Active" : "Inactive"}
                        color={manager.is_active ? "success" : "error"} size="small" variant="outlined" />
                    </TableCell>
                    <TableCell>
                      {manager.hr_copilot_sections?.length > 0 ? (
                        <Box sx={{ display: "flex", gap: 0.5, flexWrap: "wrap" }}>
                          {manager.hr_copilot_sections.map((s) => (
                            <Chip key={s} label={s} size="small" variant="outlined" />
                          ))}
                        </Box>
                      ) : (<Typography variant="caption" color="text.secondary">No scope</Typography>)}
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: "flex", gap: 0.5 }}>
                        <IconButton size="small" onClick={() => setEditDialog({ open: true, manager })}>
                          <EditIcon fontSize="small" />
                        </IconButton>
                        <IconButton size="small" onClick={() => setPasswordDialog({ open: true, manager })}>
                          <KeyIcon fontSize="small" />
                        </IconButton>
                        <IconButton size="small" color="error" onClick={() => setDeleteDialog({ open: true, manager })}>
                          <DeleteIcon fontSize="small" />
                        </IconButton>
                      </Box>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      <CreateManagerDialog open={createDialog} onClose={() => setCreateDialog(false)}
        onSubmit={(data) => createMutation.mutate(data)} loading={createMutation.isPending} />
      <EditManagerDialog open={editDialog.open} manager={editDialog.manager}
        onClose={() => setEditDialog({ open: false, manager: null })}
        onSubmit={(data) => updateMutation.mutate({ id: editDialog.manager?.id, data })}
        loading={updateMutation.isPending} />
      <ChangePasswordDialog open={passwordDialog.open} manager={passwordDialog.manager}
        onClose={() => setPasswordDialog({ open: false, manager: null })}
        onSubmit={(password) => passwordMutation.mutate({ id: passwordDialog.manager?.id, password })}
        loading={passwordMutation.isPending} />
      <DeleteManagerDialog open={deleteDialog.open} manager={deleteDialog.manager}
        onClose={() => setDeleteDialog({ open: false, manager: null })}
        onConfirm={() => deleteMutation.mutate(deleteDialog.manager?.id)}
        loading={deleteMutation.isPending} />
    </Box>
  );
}

function CreateManagerDialog({ open, onClose, onSubmit, loading }) {
  const [formData, setFormData] = useState({
    email: "", password: "", first_name: "", last_name: "",
    hr_copilot_sections: [], hr_copilot_subsections: [],
  });

  const handleSubmit = (e) => { e.preventDefault(); onSubmit(formData); };
  const handleClose = () => {
    setFormData({ email: "", password: "", first_name: "", last_name: "",
      hr_copilot_sections: [], hr_copilot_subsections: [] });
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>Create Manager Account</DialogTitle>
        <DialogContent>
          <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 1 }}>
            <Box sx={{ display: "flex", gap: 2 }}>
              <TextField label="First Name" value={formData.first_name}
                onChange={(e) => setFormData({ ...formData, first_name: e.target.value })} required fullWidth />
              <TextField label="Last Name" value={formData.last_name}
                onChange={(e) => setFormData({ ...formData, last_name: e.target.value })} required fullWidth />
            </Box>
            <TextField label="Email" type="email" value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })} required fullWidth />
            <TextField label="Password" type="password" value={formData.password}
              onChange={(e) => setFormData({ ...formData, password: e.target.value })}
              required fullWidth helperText="Minimum 8 characters" />
            <Autocomplete multiple options={AVAILABLE_SECTIONS} value={formData.hr_copilot_sections}
              onChange={(e, value) => setFormData({ ...formData, hr_copilot_sections: value })}
              renderInput={(params) => <TextField {...params} label="Sections" helperText="Sections this manager can access" />} />
            <Autocomplete multiple options={AVAILABLE_SUBSECTIONS} value={formData.hr_copilot_subsections}
              onChange={(e, value) => setFormData({ ...formData, hr_copilot_subsections: value })}
              renderInput={(params) => <TextField {...params} label="Subsections (Optional)" />} />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose} disabled={loading}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={loading}>
            {loading ? "Creating..." : "Create Manager"}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

function EditManagerDialog({ open, manager, onClose, onSubmit, loading }) {
  const [formData, setFormData] = useState({
    first_name: "", last_name: "", hr_copilot_sections: [], hr_copilot_subsections: [], is_active: true,
  });

  React.useEffect(() => {
    if (manager) {
      setFormData({
        first_name: manager.first_name || "", last_name: manager.last_name || "",
        hr_copilot_sections: manager.hr_copilot_sections || [],
        hr_copilot_subsections: manager.hr_copilot_subsections || [],
        is_active: manager.is_active ?? true,
      });
    }
  }, [manager]);

  const handleSubmit = (e) => { e.preventDefault(); onSubmit(formData); };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>Edit Manager</DialogTitle>
        <DialogContent>
          <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 1 }}>
            <Box sx={{ display: "flex", gap: 2 }}>
              <TextField label="First Name" value={formData.first_name}
                onChange={(e) => setFormData({ ...formData, first_name: e.target.value })} required fullWidth />
              <TextField label="Last Name" value={formData.last_name}
                onChange={(e) => setFormData({ ...formData, last_name: e.target.value })} required fullWidth />
            </Box>
            <Autocomplete multiple options={AVAILABLE_SECTIONS} value={formData.hr_copilot_sections}
              onChange={(e, value) => setFormData({ ...formData, hr_copilot_sections: value })}
              renderInput={(params) => <TextField {...params} label="Sections" />} />
            <Autocomplete multiple options={AVAILABLE_SUBSECTIONS} value={formData.hr_copilot_subsections}
              onChange={(e, value) => setFormData({ ...formData, hr_copilot_subsections: value })}
              renderInput={(params) => <TextField {...params} label="Subsections (Optional)" />} />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} disabled={loading}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={loading}>
            {loading ? "Updating..." : "Update Manager"}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

function ChangePasswordDialog({ open, manager, onClose, onSubmit, loading }) {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (password !== confirmPassword) { setError("Passwords do not match"); return; }
    if (password.length < 8) { setError("Password must be at least 8 characters"); return; }
    onSubmit(password);
  };

  const handleClose = () => {
    setPassword(""); setConfirmPassword(""); setError(""); onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="xs" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>Change Manager Password</DialogTitle>
        <DialogContent>
          <Box sx={{ display: "flex", flexDirection: "column", gap: 2, mt: 1 }}>
            {manager && (
              <Typography variant="body2" color="text.secondary">
                Changing password for {manager.first_name} {manager.last_name}
              </Typography>
            )}
            <TextField label="New Password" type="password" value={password}
              onChange={(e) => { setPassword(e.target.value); setError(""); }}
              required fullWidth helperText="Minimum 8 characters" />
            <TextField label="Confirm Password" type="password" value={confirmPassword}
              onChange={(e) => { setConfirmPassword(e.target.value); setError(""); }} required fullWidth />
            {error && <Alert severity="error">{error}</Alert>}
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose} disabled={loading}>Cancel</Button>
          <Button type="submit" variant="contained" disabled={loading}>
            {loading ? "Changing..." : "Change Password"}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
}

function DeleteManagerDialog({ open, manager, onClose, onConfirm, loading }) {
  return (
    <Dialog open={open} onClose={onClose} maxWidth="xs" fullWidth>
      <DialogTitle>Delete Manager</DialogTitle>
      <DialogContent>
        <Typography variant="body2">
          Are you sure you want to delete manager <strong>{manager?.first_name} {manager?.last_name}</strong>?
        </Typography>
        <Typography variant="body2" color="error" sx={{ mt: 2 }}>This action cannot be undone.</Typography>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={loading}>Cancel</Button>
        <Button onClick={onConfirm} color="error" variant="contained" disabled={loading}>
          {loading ? "Deleting..." : "Delete Manager"}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
