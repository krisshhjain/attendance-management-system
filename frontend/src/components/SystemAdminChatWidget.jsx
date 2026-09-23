import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Alert, Box, Fab, IconButton, Paper, Typography } from "@mui/material";
import SmartToyOutlinedIcon from "@mui/icons-material/SmartToyOutlined";
import CloseIcon from "@mui/icons-material/Close";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import { ChatInput } from "./hr-copilot/ChatInput.jsx";
import { ChatMessage } from "./hr-copilot/ChatMessage.jsx";
import { useOrganizationScope } from "../lib/organizationScope.jsx";

export function SystemAdminChatWidget() {
  const [open, setOpen] = useState(false);
  const [minimized, setMinimized] = useState(false);
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState([]);
  const { selectedScope } = useOrganizationScope();
  const navigate = useNavigate();

  function handleSendMessage(message, attachments = []) {
    const content = message.trim();
    if (!content && !attachments.length) return;
    setMessages((current) => [...current, {
      id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`,
      role: "user",
      content,
      attachments,
      scope: selectedScope,
      timestamp: new Date().toISOString(),
    }]);
    setDraft("");
  }

  return (
    <>
      {open && !minimized && <Paper elevation={8} sx={{ position: "fixed", right: 24, bottom: 88, zIndex: 1300, width: { xs: "calc(100vw - 32px)", sm: 360 }, height: 440, display: "flex", flexDirection: "column", overflow: "hidden", borderRadius: 3 }}>
        <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", px: 2, py: 1.5, bgcolor: "primary.main", color: "primary.contrastText" }}>
          <Typography fontWeight={700}>HR Assistant</Typography>
          <Box>
            <IconButton aria-label="Minimize assistant" size="small" onClick={() => setMinimized(true)} sx={{ color: "inherit" }}><KeyboardArrowDownIcon /></IconButton>
            <IconButton aria-label="Close assistant" size="small" onClick={() => { setOpen(false); setMinimized(false); }} sx={{ color: "inherit" }}><CloseIcon /></IconButton>
          </Box>
        </Box>
        <Alert severity="info" sx={{ mx: 1.5, mt: 1.5 }}>Preview only: messages stay in this browser session and no AI response is generated.</Alert>
        <Box sx={{ flex: 1, minHeight: 0, overflowY: "auto", px: 1.5, py: 1 }}>
          {messages.map((message) => <ChatMessage key={message.id} message={message} />)}
        </Box>
        <Box sx={{ p: 1.5 }}>
          <ChatInput value={draft} onChange={setDraft} onSend={handleSendMessage} placeholder="Write a message" />
          <Typography component="button" onClick={() => { setOpen(false); setMinimized(false); navigate({ to: "/hr-copilot" }); }} sx={{ border: 0, bgcolor: "transparent", color: "primary.main", textAlign: "left", cursor: "pointer", p: 0, mt: 1 }}>
            Open HR Copilot
          </Typography>
        </Box>
      </Paper>}
      {open && minimized && <Fab size="small" color="primary" aria-label="Restore HR assistant" onClick={() => setMinimized(false)} sx={{ position: "fixed", right: 24, bottom: 24, zIndex: 1300 }}><SmartToyOutlinedIcon /></Fab>}
      {!open && <Fab color="primary" aria-label="Open HR assistant" onClick={() => { setOpen(true); setMinimized(false); }} sx={{ position: "fixed", right: 24, bottom: 24, zIndex: 1300 }}>
        <SmartToyOutlinedIcon />
      </Fab>}
    </>
  );
}
