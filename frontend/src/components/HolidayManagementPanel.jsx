import { useCallback, useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Alert, Box, Button, Chip, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, IconButton, Paper, Switch, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField, Typography } from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import EditIcon from "@mui/icons-material/Edit";
import { createHoliday, fetchAdminHolidays, updateHoliday } from "../lib/api.js";
import { formatHolidayDate } from "../data/holidayCalendar.js";

export function HolidayManagementPanel() {
  const queryClient = useQueryClient();
  const [holidays, setHolidays] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [dialog, setDialog] = useState({ open: false, holiday: null });
  const [date, setDate] = useState("");
  const [name, setName] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setHolidays(await fetchAdminHolidays());
      setError("");
    } catch (err) {
      setError(err.message || "Could not load holidays.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const openDialog = (holiday = null) => {
    setDate(holiday?.date ?? "");
    setName(holiday?.name ?? "");
    setDialog({ open: true, holiday });
    setError("");
  };

  const save = async () => {
    setSaving(true);
    setError("");
    try {
      const values = { date, name };
      if (dialog.holiday) await updateHoliday(dialog.holiday.id, values);
      else await createHoliday(values);
      setDialog({ open: false, holiday: null });
      await queryClient.invalidateQueries({ queryKey: ["holidays", "active"] });
      await load();
    } catch (err) {
      setError(err.message || "Could not save the holiday.");
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (holiday) => {
    setError("");
    try {
      await updateHoliday(holiday.id, { is_active: !holiday.is_active });
      await queryClient.invalidateQueries({ queryKey: ["holidays", "active"] });
      await load();
    } catch (err) {
      setError(err.message || "Could not update holiday status.");
    }
  };

  return (
    <Box sx={{ p: 4 }}>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 2, mb: 3 }}>
        <Box>
          <Typography variant="h5" fontWeight={700} sx={{ color: "#0f172a" }}>Holiday Calendar</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>Manage company holiday dates. Deactivated holidays remain in the record.</Typography>
        </Box>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => openDialog()}>Add holiday</Button>
      </Box>
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError("")}>{error}</Alert>}
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead><TableRow><TableCell>Date</TableCell><TableCell>Name</TableCell><TableCell>Status</TableCell><TableCell align="right">Actions</TableCell></TableRow></TableHead>
          <TableBody>
            {loading ? <TableRow><TableCell colSpan={4} align="center"><CircularProgress size={22} /></TableCell></TableRow>
              : holidays.length === 0 ? <TableRow><TableCell colSpan={4} align="center">No holidays have been added.</TableCell></TableRow>
                : holidays.map((holiday) => <TableRow key={holiday.id}>
                  <TableCell>{formatHolidayDate(holiday.date)}</TableCell>
                  <TableCell>{holiday.name}</TableCell>
                  <TableCell><Chip size="small" label={holiday.is_active ? "Active" : "Inactive"} color={holiday.is_active ? "success" : "default"} /></TableCell>
                  <TableCell align="right">
                    <IconButton aria-label={`Edit ${holiday.name}`} onClick={() => openDialog(holiday)} size="small"><EditIcon fontSize="small" /></IconButton>
                    <Switch checked={holiday.is_active} onChange={() => toggleActive(holiday)} inputProps={{ "aria-label": `${holiday.is_active ? "Deactivate" : "Activate"} ${holiday.name}` }} size="small" />
                  </TableCell>
                </TableRow>)}
          </TableBody>
        </Table>
      </TableContainer>
      <Dialog open={dialog.open} onClose={() => !saving && setDialog({ open: false, holiday: null })} fullWidth maxWidth="xs">
        <DialogTitle>{dialog.holiday ? "Edit holiday" : "Add holiday"}</DialogTitle>
        <DialogContent sx={{ display: "grid", gap: 2, pt: "12px !important" }}>
          <TextField label="Date" type="date" value={date} onChange={(event) => setDate(event.target.value)} InputLabelProps={{ shrink: true }} inputProps={{ "aria-label": "Holiday date" }} required />
          <TextField label="Holiday name" value={name} onChange={(event) => setName(event.target.value)} inputProps={{ maxLength: 120 }} required />
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setDialog({ open: false, holiday: null })} disabled={saving}>Cancel</Button>
          <Button variant="contained" onClick={save} disabled={saving || !date || !name.trim()}>{saving ? "Saving..." : "Save"}</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
