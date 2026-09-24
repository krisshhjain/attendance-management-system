import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { Avatar, Box, Button, Divider, Drawer, IconButton, Paper, TextField, Typography } from "@mui/material";
import AddRoundedIcon from "@mui/icons-material/AddRounded";
import MenuRoundedIcon from "@mui/icons-material/MenuRounded";
import SearchRoundedIcon from "@mui/icons-material/SearchRounded";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import { RequireAuth } from "../components/RequireAuth.jsx";
import { ChatInput } from "../components/hr-copilot/ChatInput.jsx";
import { ChatMessages } from "../components/hr-copilot/ChatMessages.jsx";
import { useAuth } from "../lib/auth.jsx";
import { useOrganizationScope } from "../lib/organizationScope.jsx";
import { sendMessage } from "../services/hrCopilotService.js";

const suggestions = [
  "Show me today's attendance summary",
  "Which employees have pending leave requests?",
  "Give me an overview of recent leave trends",
  "Show attendance concerns that may need HR attention",
];

function HRCopilotPage() {
  const { user, loginType } = useAuth();
  const { selectedScope } = useOrganizationScope();
  const [conversation, setConversation] = useState({ id: null, title: "", messages: [] });
  const [draft, setDraft] = useState("");
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation.messages.length]);

  function handleNewChat() {
    setConversation({ id: null, title: "", messages: [] });
    setDraft("");
    setIsLoading(false);
    setError(null);
    setMobileSidebarOpen(false);
  }

  async function handleSendMessage(message, attachments = []) {
    const content = message.trim();
    if ((!content && !attachments.length) || isLoading) return;
    setError(null);
    const conversationId = conversation.id || `local-${Date.now()}`;
    const userMessage = {
      id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`,
      role: "user",
      content,
      attachments,
      scope: selectedScope,
      timestamp: new Date().toISOString(),
    };
    setConversation((current) => ({
      id: conversationId,
      title: current.title || content.slice(0, 64) || attachments[0]?.name || "File question",
      messages: [...current.messages, userMessage],
    }));
    setDraft("");

    if (attachments.length) {
      setConversation((current) => ({
        ...current,
        messages: [...current.messages, {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: "File analysis is not enabled yet. I kept the attachment in this chat, but it was not uploaded or processed.",
          timestamp: new Date().toISOString(),
        }],
      }));
      return;
    }

    setIsLoading(true);
    try {
      const result = await sendMessage({
        message: content,
        conversationId,
        scope: selectedScope,
      });
      setConversation((current) => ({
        ...current,
        messages: [...current.messages, {
          id: globalThis.crypto?.randomUUID?.() || `assistant-${Date.now()}`,
          role: "assistant",
          content: result.answer,
          data: result.data,
          intent: result.intent,
          queryStatus: result.query_status,
          timestamp: new Date().toISOString(),
        }],
      }));
    } catch (requestError) {
      setError(requestError.message || "Unable to complete this HR query.");
    } finally {
      setIsLoading(false);
    }
  }

  const sidebar = (
    <Box sx={{ width: 280, height: "100%", display: "flex", flexDirection: "column", bgcolor: "#f7f7f8" }}>
      <Box sx={{ p: 2 }}>
        <Button fullWidth variant="outlined" startIcon={<AddRoundedIcon />} onClick={handleNewChat} sx={{ justifyContent: "flex-start", borderColor: "divider", color: "text.primary", py: 1.1, textTransform: "none", fontWeight: 600 }}>
          New Chat
        </Button>
        <TextField
          fullWidth
          size="small"
          disabled
          placeholder="Search conversations"
          InputProps={{ startAdornment: <SearchRoundedIcon fontSize="small" sx={{ mr: 1, color: "text.disabled" }} /> }}
          sx={{ mt: 1.5, "& .MuiOutlinedInput-root": { bgcolor: "white", borderRadius: 2 } }}
        />
      </Box>
      <Typography variant="caption" fontWeight={700} color="text.secondary" sx={{ px: 2, pb: 1, textTransform: "uppercase", letterSpacing: 0.6 }}>
        Previous conversations
      </Typography>
      <Box sx={{ px: 2, py: 2, flex: 1, color: "text.secondary" }}>
        <Typography variant="body2">Your saved conversations will appear here.</Typography>
      </Box>
      <Divider />
      <Box sx={{ p: 2, display: "flex", alignItems: "center", gap: 1.25 }}>
        <Avatar sx={{ width: 34, height: 34, bgcolor: "primary.main" }}>{user?.email?.slice(0, 1).toUpperCase() || "S"}</Avatar>
        <Box sx={{ minWidth: 0 }}>
          <Typography variant="body2" fontWeight={600} noWrap>{user?.email?.split("@")[0] || "System Admin"}</Typography>
          <Typography variant="caption" color="text.secondary">System Admin</Typography>
        </Box>
      </Box>
    </Box>
  );

  if (loginType !== "systemadmin") {
    return <Paper sx={{ p: 3 }}><Typography>System Admin access is required.</Typography></Paper>;
  }

  return (
    <Box sx={{ display: "flex", height: { xs: "calc(100vh - 112px)", md: "calc(100vh - 136px)" }, minHeight: 520, overflow: "hidden", border: "1px solid", borderColor: "divider", borderRadius: 3, bgcolor: "background.paper" }}>
      <Box sx={{ display: { xs: "none", md: "block" }, flexShrink: 0 }}>{sidebar}</Box>
      <Drawer open={mobileSidebarOpen} onClose={() => setMobileSidebarOpen(false)} sx={{ display: { xs: "block", md: "none" }, "& .MuiDrawer-paper": { width: 280 } }}>{sidebar}</Drawer>

      <Box component="main" sx={{ minWidth: 0, flex: 1, display: "flex", flexDirection: "column" }}>
        <Box sx={{ height: 56, px: 2, display: "flex", alignItems: "center", gap: 1, borderBottom: "1px solid", borderColor: "divider" }}>
          <IconButton aria-label="Open conversations" onClick={() => setMobileSidebarOpen(true)} sx={{ display: { xs: "inline-flex", md: "none" } }}><MenuRoundedIcon /></IconButton>
          <AutoAwesomeIcon color="primary" fontSize="small" />
          <Typography variant="subtitle1" fontWeight={700}>HR Copilot</Typography>
          <Typography variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>Read-only HR data</Typography>
        </Box>

        <Box sx={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
          {conversation.messages.length === 0 ? (
            <Box sx={{ flex: 1, overflowY: "auto", display: "grid", placeItems: "center", px: 2, py: 4 }}>
              <Box sx={{ width: "100%", maxWidth: 680, textAlign: "center" }}>
                <Avatar sx={{ width: 56, height: 56, mx: "auto", mb: 2, bgcolor: "primary.main" }}><AutoAwesomeIcon /></Avatar>
                <Typography variant="h4" fontWeight={700} sx={{ letterSpacing: "-0.5px" }}>HR Copilot</Typography>
                <Typography color="text.secondary" sx={{ mt: 1, mb: 4 }}>A conversational workspace for HR operations and workforce insights.</Typography>
                <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" }, gap: 1.25, textAlign: "left" }}>
                  {suggestions.map((suggestion) => <Button key={suggestion} variant="outlined" onClick={() => setDraft(suggestion)} sx={{ justifyContent: "flex-start", textAlign: "left", textTransform: "none", color: "text.primary", borderColor: "divider", borderRadius: 2, minHeight: 58, px: 1.5 }}>{suggestion}</Button>)}
                </Box>
              </Box>
            </Box>
          ) : (
            <ChatMessages messages={conversation.messages} loading={isLoading} error={error} />
          )}
          <Box sx={{ px: { xs: 1.5, sm: 3 }, pt: 1.5, pb: 1.5, borderTop: "1px solid", borderColor: "divider", bgcolor: "background.paper" }}>
            <Box sx={{ maxWidth: 820, mx: "auto" }}>
              <ChatInput value={draft} onChange={setDraft} onSend={handleSendMessage} disabled={isLoading} />
              <Typography variant="caption" color="text.secondary" display="block" textAlign="center" sx={{ mt: 1 }}>Answers use HR records within your assigned organizational scope.</Typography>
            </Box>
          </Box>
          <div ref={messagesEndRef} />
        </Box>
      </Box>
    </Box>
  );
}

export const Route = createFileRoute("/hr-copilot")({
  component: () => <RequireAuth><HRCopilotPage /></RequireAuth>,
});
