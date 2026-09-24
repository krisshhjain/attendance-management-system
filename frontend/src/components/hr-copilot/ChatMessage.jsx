import { Avatar, Box, Typography } from "@mui/material";
import AttachFileOutlinedIcon from "@mui/icons-material/AttachFileOutlined";
import PersonOutlineIcon from "@mui/icons-material/PersonOutline";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";

export function ChatMessage({ message }) {
  const isUser = message.role === "user";
  return (
    <Box sx={{ display: "flex", gap: 1.5, alignItems: "flex-start", maxWidth: 820, width: "100%", mx: "auto", py: 2 }}>
      <Avatar sx={{ width: 32, height: 32, bgcolor: isUser ? "grey.200" : "primary.main", color: isUser ? "text.primary" : "primary.contrastText" }}>
        {isUser ? <PersonOutlineIcon fontSize="small" /> : <AutoAwesomeIcon fontSize="small" />}
      </Avatar>
      <Box sx={{ minWidth: 0, flex: 1 }}>
        <Typography variant="subtitle2" fontWeight={700}>{isUser ? "You" : "HR Copilot"}</Typography>
        {message.content && <Typography component="div" sx={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere", lineHeight: 1.7, mt: 0.5 }}>{message.content}</Typography>}
        {message.attachments?.length > 0 && <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75, mt: 1 }}>
          {message.attachments.map((attachment) => <Box key={attachment.id} sx={{ display: "flex", alignItems: "center", gap: 0.5, px: 1, py: 0.5, border: "1px solid", borderColor: "divider", borderRadius: 1.5, bgcolor: "action.hover", maxWidth: "100%" }}><AttachFileOutlinedIcon fontSize="small" color="action" /><Typography variant="caption" noWrap>{attachment.name}</Typography></Box>)}
        </Box>}
        <Typography variant="caption" color="text.secondary">{message.timestamp ? new Date(message.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}</Typography>
      </Box>
    </Box>
  );
}
