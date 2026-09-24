import { apiRequest } from "../lib/api.js";

export function sendMessage({ message, conversationId, scope }) {
  return apiRequest("/hr-copilot/query/", {
    method: "POST",
    body: {
      message,
      conversation_id: conversationId,
      // Sent for UI continuity only. The backend always derives authorization
      // scope from the authenticated System Admin account.
      scope,
    },
  });
}
