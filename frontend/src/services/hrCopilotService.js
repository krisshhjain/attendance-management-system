// Future backend integration boundary. This phase intentionally makes no API calls.
const notConnected = () => {
  throw new Error("HR Copilot backend integration is not available yet.");
};

export const sendMessage = notConnected;
export const getConversations = notConnected;
export const getConversation = notConnected;
export const createConversation = notConnected;
export const deleteConversation = notConnected;
