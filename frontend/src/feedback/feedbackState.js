export const FEEDBACK_SEVERITIES = ["success", "error", "warning", "info"];

export const DEFAULT_DURATIONS = {
  success: 4200,
  error: 6500,
  warning: 5200,
  info: 4200,
};

const DEFAULT_TITLES = {
  success: "Success",
  error: "Something went wrong",
  warning: "Please note",
  info: "Information",
};

export function getFeedbackKey(notification) {
  return notification.dedupeKey || `${notification.severity}:${notification.title}:${notification.message}`;
}

export function createNotification(input, id) {
  const severity = FEEDBACK_SEVERITIES.includes(input?.severity) ? input.severity : "info";
  const message = String(input?.message ?? "").trim();

  if (!message) return null;

  const duration = input?.duration === 0
    ? 0
    : Math.max(0, Number(input?.duration ?? DEFAULT_DURATIONS[severity]) || 0);

  return {
    id,
    severity,
    title: String(input?.title || DEFAULT_TITLES[severity]),
    message,
    duration,
    dedupeKey: input?.dedupeKey,
  };
}

export function enqueueNotification(state, notification) {
  if (!notification) return state;

  const key = getFeedbackKey(notification);
  if (state.some((item) => getFeedbackKey(item) === key)) return state;

  return [...state, notification];
}

export function removeNotification(state, id) {
  return state.filter((item) => item.id !== id);
}
