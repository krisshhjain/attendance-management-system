import { Avatar, Box, Button, Chip, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from "@mui/material";
import AttachFileOutlinedIcon from "@mui/icons-material/AttachFileOutlined";
import PersonOutlineIcon from "@mui/icons-material/PersonOutline";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";

export function ChatMessage({ message, onAction, busyActionId }) {
  const isUser = message.role === "user";
  const displayDate = (value) => {
    if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return value;
    const [year, month, day] = value.split("-").map(Number);
    return new Date(year, month - 1, day).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" });
  };
  return (
    <Box sx={{ display: "flex", gap: 1.5, alignItems: "flex-start", maxWidth: 820, width: "100%", mx: "auto", py: 2 }}>
      <Avatar sx={{ width: 32, height: 32, bgcolor: isUser ? "grey.200" : "primary.main", color: isUser ? "text.primary" : "primary.contrastText" }}>
        {isUser ? <PersonOutlineIcon fontSize="small" /> : <AutoAwesomeIcon fontSize="small" />}
      </Avatar>
      <Box sx={{ minWidth: 0, flex: 1 }}>
        <Typography variant="subtitle2" fontWeight={700}>{isUser ? "You" : "HR Copilot"}</Typography>
        {message.content && <Typography component="div" sx={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", lineHeight: 1.7, mt: 0.5 }}>{message.content}</Typography>}
        {message.data?.columns?.length > 0 && message.data?.rows?.length > 0 && (
          <TableContainer component={Paper} variant="outlined" sx={{ mt: 1.5, maxHeight: 320, borderRadius: 2 }}>
            <Table size="small" stickyHeader aria-label="HR Copilot query results">
              <TableHead><TableRow>{message.data.columns.map((column) => <TableCell key={column} sx={{ fontWeight: 700, whiteSpace: "nowrap" }}>{column.replaceAll("_", " ")}</TableCell>)}</TableRow></TableHead>
              <TableBody>{message.data.rows.map((row, index) => <TableRow key={`${message.id}-row-${index}`} hover>{message.data.columns.map((column) => <TableCell key={column} sx={{ whiteSpace: "nowrap" }}>{row[column] == null ? "—" : String(row[column])}</TableCell>)}</TableRow>)}</TableBody>
            </Table>
          </TableContainer>
        )}
        {message.pendingAction && (
          <Paper variant="outlined" sx={{ mt: 1.25, p: 1.5, borderColor: "warning.light", bgcolor: "warning.50" }}>
            {message.pendingAction.status === "PENDING" ? <>
              <Box sx={{ display: "flex", gap: 1, alignItems: "center", mb: 0.75 }}>
                <Chip size="small" color="warning" label="Approval required" />
              </Box>
              <Typography variant="subtitle2" fontWeight={700}>{message.pendingAction.action_type?.startsWith("leave") ? "Leave Request" : "Attendance Change"}</Typography>
              <Box sx={{ display: "grid", gridTemplateColumns: "110px minmax(0, 1fr)", gap: 0.5, mt: 0.75 }}>
                {[
                  ["Employee", message.pendingAction.target_data?.employee_name],
                  ["Date", displayDate(message.pendingAction.target_data?.date || message.pendingAction.target_data?.start_date)],
                  ["Status", message.pendingAction.proposed_changes?.status || message.pendingAction.target_data?.target_status],
                  ["Check-in", message.pendingAction.proposed_changes?.check_in_time || (["LEAVE", "ABSENT"].includes(message.pendingAction.proposed_changes?.status) ? "Will be cleared" : null)],
                  ["Check-out", message.pendingAction.proposed_changes?.check_out_time || (["LEAVE", "ABSENT"].includes(message.pendingAction.proposed_changes?.status) ? "Will be cleared" : null)],
                  ["Reason", message.pendingAction.target_data?.reason || message.pendingAction.proposed_changes?.reason],
                ].filter(([, value]) => value).map(([label, value]) => (
                  <Box key={label} sx={{ display: "contents" }}>
                    <Typography variant="caption" color="text.secondary">{label}</Typography>
                    <Typography variant="body2" fontWeight={600}>{String(value)}</Typography>
                  </Box>
                ))}
              </Box>
              {message.pendingAction.warning_message && <Typography variant="body2" color="warning.dark" sx={{ mt: 0.75 }}>{message.pendingAction.warning_message}</Typography>}
              <Box sx={{ display: "flex", gap: 1, mt: 1.25 }}>
                <Button size="small" variant="contained" onClick={() => onAction?.(message.pendingAction.action_id, "approve")} disabled={Boolean(busyActionId)}>{busyActionId === message.pendingAction.action_id ? "Working…" : "Approve change"}</Button>
                <Button size="small" onClick={() => onAction?.(message.pendingAction.action_id, "cancel")} disabled={Boolean(busyActionId)}>Cancel</Button>
              </Box>
            </> : message.pendingAction.status === "AWAITING_INFORMATION" ? <>
              <Chip size="small" color="info" label="Waiting for details" />
              <Button size="small" sx={{ ml: 1 }} onClick={() => onAction?.(message.pendingAction.action_id, "cancel")} disabled={Boolean(busyActionId)}>Cancel</Button>
            </> : <Chip
              size="small"
              color={message.pendingAction.status === "EXECUTED" ? "success" : "default"}
              label={message.pendingAction.status === "CANCELLED" ? "Cancelled · no changes made" : message.pendingAction.status === "EXECUTED" ? "Change applied" : message.pendingAction.status}
            />}
          </Paper>
        )}
        {message.attachments?.length > 0 && <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75, mt: 1 }}>
          {message.attachments.map((attachment) => <Box key={attachment.id} sx={{ display: "flex", alignItems: "center", gap: 0.5, px: 1, py: 0.5, border: "1px solid", borderColor: "divider", borderRadius: 1.5, bgcolor: "action.hover", maxWidth: "100%" }}><AttachFileOutlinedIcon fontSize="small" color="action" /><Typography variant="caption" noWrap>{attachment.name}</Typography></Box>)}
        </Box>}
        <Typography variant="caption" color="text.secondary">{message.timestamp ? new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}</Typography>
      </Box>
    </Box>
  );
}
