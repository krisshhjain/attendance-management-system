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
import { fetchConversation, respondToAction, sendMessage } from "../services/hrCopilotService.js";
import { useFeedback } from "../feedback/FeedbackProvider.jsx";
import { createClientId } from "../lib/clientId.js";

const suggestions = [
  "Show me today's attendance summary",
  "Which employees have pending leave requests?",
  "Give me an overview of recent leave trends",
  "Who all were absent yesterday?",
];

function HRCopilotPage() {
  const { user, loginType } = useAuth();
  const { selectedScope } = useOrganizationScope();
  const [conversation, setConversation] = useState({ id: null, title: "", messages: [] });
  const [draft, setDraft] = useState("");
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [busyActionId, setBusyActionId] = useState(null);
  const messagesEndRef = useRef(null);
  const sendingRef = useRef(false);
  const conversationRef = useRef(conversation);
  const restoredPendingActions = useRef(false);
  const { success, notifyError } = useFeedback();

  useEffect(() => { conversationRef.current = conversation; }, [conversation]);

  useEffect(() => {
    if (loginType !== "systemadmin" || restoredPendingActions.current || !user?.id) return;
    restoredPendingActions.current = true;
    const storageKey = `hr-copilot-current-${user.id}`;
    const conversationId = globalThis.sessionStorage?.getItem(storageKey);
    if (!conversationId) return;
    fetchConversation(conversationId).then(({ messages = [] }) => {
      const restoredMessages = messages.map((message) => ({
        ...message,
        pendingAction: message.pending_action || message.pendingAction || null,
      }));
      const restored = { id: conversationId, title: messages.find((message) => message.role === "user")?.content?.slice(0, 64) || "", messages: restoredMessages };
      conversationRef.current = restored;
      setConversation(restored);
    }).catch((historyError) => setError(historyError.message || "Conversation history could not be loaded."));
  }, [loginType, user?.id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation.messages.length]);

  function handleNewChat() {
    const nextConversation = { id: globalThis.crypto?.randomUUID?.() || `conversation-${Date.now()}`, title: "", messages: [] };
    if (user?.id) globalThis.sessionStorage?.setItem(`hr-copilot-current-${user.id}`, nextConversation.id);
    conversationRef.current = nextConversation;
    setConversation(nextConversation);
    setDraft("");
    setIsLoading(false);
    setError(null);
    setMobileSidebarOpen(false);
  }

  async function handleSendMessage(message, attachments = []) {
    const content = message.trim();
    if ((!content && !attachments.length) || isLoading || sendingRef.current) return;
    if (!content) {
      setError("Please include a text question. File contents are not sent to the HR database assistant.");
      return;
    }
    setError(null);
    const activeConversationId = conversationRef.current.id || createClientId();
    if (user?.id) globalThis.sessionStorage?.setItem(`hr-copilot-current-${user.id}`, activeConversationId);
    const userMessage = {
      id: createClientId(),
      role: "user",
      content,
      attachments,
      scope: selectedScope,
      timestamp: new Date().toISOString(),
    };
    const nextConversation = {
      ...conversationRef.current,
      id: activeConversationId,
      title: conversationRef.current.title || content.slice(0, 64),
      messages: [...conversationRef.current.messages, userMessage],
    };
    conversationRef.current = nextConversation;
    setConversation(nextConversation);
    setDraft("");
    sendingRef.current = true;
    setIsLoading(true);
    try {
      const response = await sendMessage({ message: content, conversationId: activeConversationId, scope: selectedScope });
      if (response.conversation_id && user?.id) globalThis.sessionStorage?.setItem(`hr-copilot-current-${user.id}`, response.conversation_id);
      if (conversationRef.current.id !== activeConversationId) return;
      const assistantMessage = {
        id: createClientId(),
        role: "assistant",
        content: response.answer || "I couldn't complete that request.",
        data: response.data,
        pendingAction: response.pending_action ? { ...response.pending_action, status: response.pending_action.status || (response.query_status === "pending_approval" ? "PENDING" : "AWAITING_INFORMATION") } : null,
        timestamp: new Date().toISOString(),
      };
      const updated = { ...conversationRef.current, messages: [...conversationRef.current.messages, assistantMessage] };
      conversationRef.current = updated;
      setConversation(updated);
    } catch (requestError) {
      if (conversationRef.current.id === activeConversationId) setError(requestError.message || "The HR Copilot request failed.");
    } finally {
      sendingRef.current = false;
      setIsLoading(false);
    }
  }

  async function handlePendingAction(actionId, action) {
    if (busyActionId) return;
    setBusyActionId(actionId);
    setError(null);
    try {
      const response = await respondToAction({ actionId, action, conversationId: conversationRef.current.id });
      const updated = {
        ...conversationRef.current,
        messages: conversationRef.current.messages.map((message) => message.pendingAction?.action_id === actionId
          ? { ...message, content: response.answer || message.content, pendingAction: { ...message.pendingAction, status: action === "approve" ? "EXECUTED" : "CANCELLED" }, timestamp: new Date().toISOString() }
          : message),
      };
      conversationRef.current = updated;
      setConversation(updated);
      success(action === "approve" ? "Action completed successfully." : "Action cancelled successfully.");
    } catch (actionError) {
      notifyError(actionError, { title: "Copilot action failed", fallback: "We couldn't complete that action. Please try again." });
    } finally {
      setBusyActionId(null);
    }
  }

  const sidebar = (
    <Box sx={{ width: 280, height: "100%", display: "flex", flexDirection: "column", bgcolor: "#f7f7f8" }}>
      <Box sx={{ p: 2 }}>
        <Button fullWidth variant="outlined" startIcon={<AddRoundedIcon />} onClick={handleNewChat} disabled={isLoading || Boolean(busyActionId)} sx={{ justifyContent: "flex-start", borderColor: "divider", color: "text.primary", py: 1.1, textTransform: "none", fontWeight: 600 }}>
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
          <Typography variant="body2" fontWeight={600} noWrap>{user?.email?.split("@")[0] || "System Manager"}</Typography>
          <Typography variant="caption" color="text.secondary">System Manager</Typography>
        </Box>
      </Box>
    </Box>
  );

  if (loginType !== "systemadmin") {
    return <Paper sx={{ p: 3 }}><Typography>System Manager access is required.</Typography></Paper>;
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
          <Typography variant="caption" color="text.secondary" sx={{ ml: 0.5 }}>Connected</Typography>
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
            <ChatMessages messages={conversation.messages} loading={isLoading} error={error} onAction={handlePendingAction} busyActionId={busyActionId} />
          )}
          <Box sx={{ px: { xs: 1.5, sm: 3 }, pt: 1.5, pb: 1.5, borderTop: "1px solid", borderColor: "divider", bgcolor: "background.paper" }}>
            <Box sx={{ maxWidth: 820, mx: "auto" }}>
              <ChatInput value={draft} onChange={setDraft} onSend={handleSendMessage} disabled={isLoading} />
              <Typography variant="caption" color="text.secondary" display="block" textAlign="center" sx={{ mt: 1 }}>HR records are accessed using your System Manager permissions. Changes require your approval.</Typography>
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
