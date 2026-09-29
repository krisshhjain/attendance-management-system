import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Chip,
  CircularProgress,
  Drawer,
  IconButton,
  MenuItem,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import RefreshIcon from "@mui/icons-material/Refresh";
import SearchIcon from "@mui/icons-material/Search";
import DownloadIcon from "@mui/icons-material/Download";
import { RequireAuth } from "../components/RequireAuth.jsx";
import { useAuth } from "../lib/auth.jsx";
import { downloadSystemLogs, fetchSystemLogActors, fetchSystemLogs } from "../lib/api.js";

export const Route = createFileRoute("/system-logs")({
  validateSearch: (search) => ({
    search: typeof search.search === "string" ? search.search : "",
    category: typeof search.category === "string" ? search.category : "",
    event_type: typeof search.event_type === "string" ? search.event_type : "",
    severity: typeof search.severity === "string" ? search.severity : "",
    status: typeof search.status === "string" ? search.status : "",
    source: typeof search.source === "string" ? search.source : "",
    actor: typeof search.actor === "string" ? search.actor : "",
    actor_role: typeof search.actor_role === "string" ? search.actor_role : "",
    date_from: typeof search.date_from === "string" ? search.date_from : "",
    date_to: typeof search.date_to === "string" ? search.date_to : "",
    page: Math.max(1, Number(search.page) || 1),
    page_size: Math.min(100, Math.max(1, Number(search.page_size) || 50)),
  }),
  component: () => (
    <RequireAuth>
      <SystemLogsPage />
    </RequireAuth>
  ),
});

const categories = ["AUTHENTICATION", "EMPLOYEE", "ATTENDANCE", "REGULARIZATION", "LEAVE", "ADMINISTRATION", "NOTIFICATION", "HR_COPILOT", "CELERY", "SECURITY"];
const severities = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"];
const statuses = ["SUCCESS", "FAILED", "DENIED", "PENDING", "RETRY", "CANCELLED", "SKIPPED"];
const sources = ["API", "ADMIN", "MOBILE", "KIOSK", "FACE_WEB", "FACE_SERVICE", "CELERY", "SYSTEM", "HR_COPILOT"];
const actorRoles = ["EMPLOYEE", "MANAGER", "STAFF", "SUPERUSER", "USER", "SYSTEM", "ANONYMOUS"];
const eventTypes = [
  "LOGIN_SUCCESS", "LOGIN_FAILED", "PASSWORD_CHANGED", "UNAUTHORIZED_ACCESS", "FORBIDDEN_ACCESS",
  "EMPLOYEE_CREATED", "EMPLOYEE_UPDATED", "EMPLOYEE_ACTIVATED", "EMPLOYEE_DEACTIVATED", "EMPLOYEE_PASSWORD_CHANGED", "FACE_ENROLLMENT",
  "MANAGER_CREATED", "MANAGER_UPDATED", "MANAGER_ACTIVATED", "MANAGER_DEACTIVATED", "MANAGER_PASSWORD_CHANGED", "ACCESS_CHANGED", "ROLE_CHANGED",
  "CHECK_IN", "CHECK_OUT", "FACE_VERIFY", "ADMIN_FORCE_CHECKOUT", "ATTENDANCE_RESET", "ATTENDANCE_EDIT", "ABSENCE_DETECTED",
  "REGULARIZATION_CREATED", "REGULARIZATION_APPROVED", "REGULARIZATION_REJECTED", "REGULARIZATION_QUOTA_CHANGED",
  "SHIFT_ASSIGNED", "SHIFT_BULK_ASSIGNED", "SHIFT_CONFIGURATION_CHANGED", "OFFICE_LOCATION_CREATED", "OFFICE_LOCATION_UPDATED", "OFFICE_LOCATION_DELETED",
  "LEAVE_CREATED", "LEAVE_UPDATED", "LEAVE_APPROVED", "LEAVE_DENIED", "LEAVE_CANCELLED", "LEAVE_TYPE_CREATED", "LEAVE_TYPE_UPDATED", "LEAVE_TYPE_DELETED", "LEAVE_POLICY_CREATED", "LEAVE_POLICY_UPDATED", "LEAVE_POLICY_DELETED",
  "NOTIFICATION_CREATED", "NOTIFICATION_READ", "NOTIFICATION_DELETED", "EMAIL_QUEUED", "EMAIL_SENT", "EMAIL_FAILED", "EMAIL_RETRY",
  "COPILOT_CONVERSATION", "COPILOT_QUERY_FAILED", "COPILOT_ACTION_REQUESTED", "COPILOT_ACTION_CONFIRMED", "COPILOT_ACTION_EXECUTED", "COPILOT_ACTION_FAILED", "COPILOT_ACTION_CANCELLED", "COPILOT_ACTION_EXPIRED",
  "TASK_STARTED", "TASK_SUCCESS", "TASK_FAILED", "TASK_RETRY",
];

function chipColor(value) {
  if (["SUCCESS", "INFO"].includes(value)) return "success";
  if (["FAILED", "ERROR", "CRITICAL", "DENIED"].includes(value)) return "error";
  if (["WARNING", "PENDING", "RETRY"].includes(value)) return "warning";
  return "default";
}

function formatDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}

function jsonText(value) {
  if (value === null || value === undefined || value === "") return "-";
  return typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

function SystemLogsPage() {
  const { user } = useAuth();
  const search = Route.useSearch();
  const navigate = Route.useNavigate();
  const [searchInput, setSearchInput] = useState(search.search);
  const [logs, setLogs] = useState({ count: 0, next: null, previous: null, results: [] });
  const [selectedLog, setSelectedLog] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reloadToken, setReloadToken] = useState(0);
  const [actorInput, setActorInput] = useState(search.actor);
  const [actorOptions, setActorOptions] = useState([]);
  const [exporting, setExporting] = useState("");

  const updateSearch = (updates) => {
    navigate({
      search: (previous) => ({ ...previous, ...updates, page: updates.page ?? 1 }),
    });
  };

  useEffect(() => {
    setSearchInput(search.search);
  }, [search.search]);

  useEffect(() => {
    if (!search.actor) setActorInput("");
  }, [search.actor]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      fetchSystemLogActors(actorInput)
        .then((options) => setActorOptions(Array.isArray(options) ? options : []))
        .catch(() => setActorOptions([]));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [actorInput]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (searchInput !== search.search) updateSearch({ search: searchInput });
    }, 350);
    return () => window.clearTimeout(timer);
  }, [searchInput, search.search]);

  const queryParams = {
    search: search.search,
    category: search.category,
    event_type: search.event_type,
    severity: search.severity,
    status: search.status,
    source: search.source,
    actor: search.actor,
    actor_role: search.actor_role,
    date_from: search.date_from,
    date_to: search.date_to,
    page: search.page,
    page_size: search.page_size,
  };
  const queryKey = JSON.stringify(queryParams);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    fetchSystemLogs(queryParams)
      .then((payload) => {
        if (active) setLogs(payload ?? { count: 0, next: null, previous: null, results: [] });
      })
      .catch((loadError) => {
        if (active) setError(loadError.message || "System Logs could not be loaded.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [queryKey, reloadToken]);

  if (!user?.is_superuser) {
    return <Alert severity="warning">You do not have access to System Logs.</Alert>;
  }

  const resetFilters = () => {
    setSearchInput("");
    navigate({ search: {} });
    setSelectedLog(null);
  };

  const exportLogs = async (format) => {
    setExporting(format);
    setError("");
    const exportParams = { ...queryParams };
    delete exportParams.page;
    delete exportParams.page_size;
    try {
      const download = await downloadSystemLogs(exportParams, format);
      const url = URL.createObjectURL(download.blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = download.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (exportError) {
      setError(exportError.message || "The export could not be generated.");
    } finally {
      setExporting("");
    }
  };

  const activeFilters = [
    ["search", search.search ? `Search: ${search.search}` : ""],
    ["category", search.category],
    ["event_type", search.event_type],
    ["severity", search.severity],
    ["status", search.status],
    ["source", search.source],
    ["actor", search.actor ? `Actor #${search.actor}` : ""],
    ["actor_role", search.actor_role],
    ["date_from", search.date_from ? `From ${search.date_from}` : ""],
    ["date_to", search.date_to ? `To ${search.date_to}` : ""],
  ].filter(([, label]) => label);

  const filterField = (name, label, values) => (
    <TextField
      key={name}
      select
      size="small"
      label={label}
      value={search[name]}
      onChange={(event) => updateSearch({ [name]: event.target.value })}
      sx={{ minWidth: { xs: "100%", sm: 160 }, flex: 1 }}
    >
      <MenuItem value="">All</MenuItem>
      {values.map((value) => <MenuItem key={value} value={value}>{value}</MenuItem>)}
    </TextField>
  );

  return (
    <Box sx={{ width: "100%", maxWidth: 1600, mx: "auto", p: { xs: 2, md: 4 }, color: "text.primary" }}>
      <Box sx={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 2, flexWrap: "wrap", mb: 3 }}>
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 750 }}>System Logs</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
            Review immutable security and operational activity.
          </Typography>
        </Box>
        <Box sx={{ display: "flex", gap: 1, alignItems: "center", flexWrap: "wrap" }}>
          <Tooltip title="Refresh logs">
            <IconButton onClick={() => setReloadToken((value) => value + 1)} aria-label="Refresh logs">
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          <Button size="small" variant="outlined" startIcon={<DownloadIcon />} disabled={Boolean(exporting)} onClick={() => exportLogs("csv")}>
            {exporting === "csv" ? "Preparing..." : "CSV"}
          </Button>
          <Button size="small" variant="contained" startIcon={<DownloadIcon />} disabled={Boolean(exporting)} onClick={() => exportLogs("xlsx")}>
            {exporting === "xlsx" ? "Preparing..." : "Excel"}
          </Button>
        </Box>
      </Box>

      <Paper variant="outlined" sx={{ p: 2, mb: 2, borderColor: "divider", bgcolor: "background.paper" }}>
        <Box sx={{ display: "flex", gap: 1, alignItems: "center", mb: 1.5 }}>
          <SearchIcon color="action" />
          <TextField
            fullWidth
            size="small"
            label="Search logs"
            placeholder="Actor, target, event, message, request ID"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
          />
        </Box>
        <Box sx={{ display: "flex", gap: 1, flexWrap: "wrap" }}>
          {filterField("category", "Category", categories)}
          {filterField("event_type", "Event", eventTypes)}
          {filterField("severity", "Severity", severities)}
          {filterField("status", "Status", statuses)}
          {filterField("source", "Source", sources)}
          {filterField("actor_role", "Actor role", actorRoles)}
          <Autocomplete
            freeSolo
            size="small"
            options={actorOptions}
            value={actorOptions.find((option) => String(option.id) === String(search.actor)) || null}
            inputValue={actorInput}
            getOptionLabel={(option) => typeof option === "string" ? option : `${option.name} (${option.email})`}
            onInputChange={(_, value, reason) => {
              setActorInput(value);
              if (reason === "clear") updateSearch({ actor: "" });
            }}
            onChange={(_, option) => {
              if (!option) {
                updateSearch({ actor: "" });
                setActorInput("");
                return;
              }
              updateSearch({ actor: String(option.id) });
              setActorInput(`${option.name} (${option.email})`);
            }}
            renderInput={(params) => <TextField {...params} label="Actor" placeholder="Search users" />}
            sx={{ minWidth: { xs: "100%", sm: 230 }, flex: 1 }}
          />
          <TextField
            size="small"
            type="date"
            label="From"
            value={search.date_from}
            onChange={(event) => updateSearch({ date_from: event.target.value })}
            InputLabelProps={{ shrink: true }}
            sx={{ minWidth: { xs: "100%", sm: 150 }, flex: 1 }}
          />
          <TextField
            size="small"
            type="date"
            label="To"
            value={search.date_to}
            onChange={(event) => updateSearch({ date_to: event.target.value })}
            InputLabelProps={{ shrink: true }}
            sx={{ minWidth: { xs: "100%", sm: 150 }, flex: 1 }}
          />
        </Box>
        <Box sx={{ display: "flex", gap: 1, alignItems: "center", flexWrap: "wrap", mt: 1.5 }}>
          <Button onClick={resetFilters} size="small">Reset Filters</Button>
          {activeFilters.length > 0 && <Typography variant="caption" color="text.secondary">{activeFilters.length} active filter{activeFilters.length === 1 ? "" : "s"}</Typography>}
        </Box>
        {activeFilters.length > 0 && (
          <Box sx={{ display: "flex", gap: 0.75, flexWrap: "wrap", mt: 1 }}>
            {activeFilters.map(([key, label]) => (
              <Chip key={key} size="small" label={label} onDelete={() => {
                if (key === "actor") setActorInput("");
                updateSearch({ [key]: "" });
              }} />
            ))}
          </Box>
        )}
      </Paper>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} action={<Button color="inherit" onClick={() => setReloadToken((value) => value + 1)}>Retry</Button>}>
          {error}
        </Alert>
      )}

      <Paper variant="outlined" sx={{ overflow: "hidden", borderColor: "divider", bgcolor: "background.paper" }}>
        {loading ? (
          <Box sx={{ minHeight: 320, display: "grid", placeItems: "center" }}><CircularProgress /></Box>
        ) : logs.results.length === 0 ? (
          <Box sx={{ minHeight: 320, display: "grid", placeItems: "center", p: 3 }}>
            <Typography color="text.secondary">No logs match the current filters.</Typography>
          </Box>
        ) : (
          <TableContainer sx={{ maxHeight: "calc(100vh - 360px)" }}>
            <Table stickyHeader size="small" sx={{ minWidth: 1120 }}>
              <TableHead>
                <TableRow>
                  {["Timestamp", "Severity", "Category", "Event", "Actor", "Target", "Status", "Source", "Message"].map((heading) => (
                    <TableCell key={heading}>{heading}</TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {logs.results.map((log) => (
                  <TableRow key={log.id} hover onClick={() => setSelectedLog(log)} sx={{ cursor: "pointer" }}>
                    <TableCell sx={{ whiteSpace: "nowrap" }}>{formatDate(log.timestamp)}</TableCell>
                    <TableCell><Chip size="small" label={log.severity} color={chipColor(log.severity)} /></TableCell>
                    <TableCell>{log.category}</TableCell>
                    <TableCell sx={{ fontWeight: 650 }}>{log.event_type}</TableCell>
                    <TableCell>{log.actor?.name || log.actor?.email || log.actor_role || "System"}</TableCell>
                    <TableCell>{log.target_label || log.target_id || "-"}</TableCell>
                    <TableCell><Chip size="small" label={log.status} color={chipColor(log.status)} /></TableCell>
                    <TableCell>{log.source}</TableCell>
                    <TableCell sx={{ maxWidth: 300, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{log.message}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
        {!loading && logs.results.length > 0 && (
          <TablePagination
            component="div"
            count={logs.count}
            page={search.page - 1}
            onPageChange={(_, page) => updateSearch({ page: page + 1 })}
            rowsPerPage={search.page_size}
            onRowsPerPageChange={(event) => updateSearch({ page_size: Number(event.target.value), page: 1 })}
            rowsPerPageOptions={[25, 50, 100]}
          />
        )}
      </Paper>

      <Drawer anchor="right" open={Boolean(selectedLog)} onClose={() => setSelectedLog(null)}>
        {selectedLog && (
          <Box sx={{ width: { xs: "100vw", sm: 520 }, p: 3, bgcolor: "background.paper", color: "text.primary", minHeight: "100%" }}>
            <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
              <Box>
                <Typography variant="h6" sx={{ fontWeight: 750 }}>{selectedLog.event_type}</Typography>
                <Typography variant="caption" color="text.secondary">Log #{selectedLog.id}</Typography>
              </Box>
              <IconButton onClick={() => setSelectedLog(null)} aria-label="Close log details"><CloseIcon /></IconButton>
            </Box>
            <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 1.5, mb: 2 }}>
              {[
                ["Timestamp", formatDate(selectedLog.timestamp)],
                ["Severity", selectedLog.severity],
                ["Category", selectedLog.category],
                ["Status", selectedLog.status],
                ["Source", selectedLog.source],
                ["Actor", selectedLog.actor?.email || selectedLog.actor_role || "System"],
                ["Target", selectedLog.target_label || selectedLog.target_id || "-"],
                ["Request ID", selectedLog.request_id || "-"],
                ["IP address", selectedLog.ip_address || "-"],
                ["User agent", selectedLog.user_agent || "-"],
              ].map(([label, value]) => (
                <Box key={label} sx={{ minWidth: 0 }}>
                  <Typography variant="caption" color="text.secondary">{label}</Typography>
                  <Typography variant="body2" sx={{ overflowWrap: "anywhere" }}>{value}</Typography>
                </Box>
              ))}
            </Box>
            <Typography variant="subtitle2" sx={{ mb: 0.5 }}>Message</Typography>
            <Typography variant="body2" sx={{ mb: 2, whiteSpace: "pre-wrap" }}>{selectedLog.message || "-"}</Typography>
            {["before_state", "after_state", "metadata"].map((field) => (
              <Box key={field} sx={{ mb: 2 }}>
                <Typography variant="subtitle2" sx={{ mb: 0.5 }}>{field.replace("_", " ")}</Typography>
                <Box component="pre" sx={{ m: 0, p: 1.5, maxHeight: 220, overflow: "auto", whiteSpace: "pre-wrap", overflowWrap: "anywhere", bgcolor: "action.hover", borderRadius: 1, fontSize: 12, fontFamily: "monospace" }}>
                  {jsonText(selectedLog[field])}
                </Box>
              </Box>
            ))}
          </Box>
        )}
      </Drawer>
    </Box>
  );
}
