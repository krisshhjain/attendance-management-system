import { apiRequest } from "../lib/api.js";

export function fetchPendingActions() {
  return apiRequest("/hr-copilot/actions/pending/");
}

export function fetchConversation(conversationId) {
  return apiRequest(`/hr-copilot/conversations/${encodeURIComponent(conversationId)}/`);
}

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

export function respondToAction({ actionId, action }) {
  return apiRequest("/hr-copilot/actions/approve/", {
    method: "POST",
    body: { action_id: actionId, action },
  });
}
