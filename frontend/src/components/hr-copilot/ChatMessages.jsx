import { Box } from "@mui/material";
import { ChatMessage } from "./ChatMessage.jsx";
import { TypingIndicator } from "./TypingIndicator.jsx";
import { ChatError } from "./ChatError.jsx";

export function ChatMessages({ messages, loading = false, error = null }) {
  return (
    <Box sx={{ flex: 1, minHeight: 0, overflowY: "auto", px: { xs: 2, md: 4 }, scrollBehavior: "smooth" }}>
      <Box sx={{ maxWidth: 820, mx: "auto", py: 2 }}>
        {messages.map((message) => <ChatMessage key={message.id} message={message} />)}
        {loading && <TypingIndicator />}
        {error && <ChatError message={error} />}
      </Box>
    </Box>
  );
}
