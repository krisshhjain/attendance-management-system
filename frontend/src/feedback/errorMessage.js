const SAFE_FALLBACK = "Something went wrong. Please try again.";

function cleanMessage(value) {
  if (typeof value !== "string") return null;
  if (/<[^>]*>/.test(value)) return null;

  const withoutMarkup = value.replace(/\s+/g, " ").trim();
  if (!withoutMarkup || withoutMarkup.length > 260) return null;
  if (/\b(stack trace|traceback| at [\w$.[\]()]+|<!doctype|<html)/i.test(withoutMarkup)) return null;
  if (/\bbearer\s+\S+|\b(access[_ -]?token|refresh[_ -]?token|password|secret)\s*[:=]/i.test(withoutMarkup)) return null;

  return withoutMarkup;
}

export function getErrorMessage(error, fallback = SAFE_FALLBACK) {
  if (!error) return fallback;

  // ApiError already contains the safe message produced by api.js/friendlyMessage().
  const apiMessage = cleanMessage(error.message);
  if (apiMessage) return apiMessage;

  if (error.status === 0) return "Unable to reach the server. Check your connection and try again.";
  if (error.status === 401) return "Your session has expired. Please sign in again.";
  if (error.status === 403) return "You do not have permission to complete this action.";
  if (error.status === 409) return "This change conflicts with newer data. Refresh and try again.";
  if (error.status === 429) return "Too many requests. Please wait a moment and try again.";
  if (error.status >= 500) return "The server is unavailable right now. Please try again.";

  return cleanMessage(fallback) || SAFE_FALLBACK;
}

export const errorToUserMessage = getErrorMessage;
