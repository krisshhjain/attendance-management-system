import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import { FeedbackToastHost } from "./FeedbackToastHost.jsx";
import { createNotification, enqueueNotification, removeNotification } from "./feedbackState.js";
import { getErrorMessage } from "./errorMessage.js";

const FeedbackContext = createContext(null);

export function FeedbackProvider({ children }) {
  const [notifications, setNotifications] = useState([]);
  const nextId = useRef(0);

  const close = useCallback((id) => {
    setNotifications((current) => removeNotification(current, id));
  }, []);

  const enqueue = useCallback((input) => {
    const notification = createNotification(input, `feedback-${nextId.current++}`);
    if (!notification) return null;

    setNotifications((current) => enqueueNotification(current, notification));
    return notification.id;
  }, []);

  const notifyError = useCallback((error, options = {}) => {
    return enqueue({
      severity: "error",
      title: options.title || "Unable to complete action",
      message: getErrorMessage(error, options.fallback),
      ...options,
    });
  }, [enqueue]);

  const value = useMemo(() => ({
    enqueue,
    notify: enqueue,
    success: (message, options = {}) => enqueue({ ...options, severity: "success", message }),
    error: (message, options = {}) => enqueue({ ...options, severity: "error", message }),
    warning: (message, options = {}) => enqueue({ ...options, severity: "warning", message }),
    info: (message, options = {}) => enqueue({ ...options, severity: "info", message }),
    notifyError,
    close,
    closeAll: () => setNotifications([]),
  }), [close, enqueue, notifyError]);

  return (
    <FeedbackContext.Provider value={value}>
      {children}
      <FeedbackToastHost notifications={notifications} onClose={close} />
    </FeedbackContext.Provider>
  );
}

export function useFeedback() {
  const context = useContext(FeedbackContext);
  if (!context) throw new Error("useFeedback must be used within a FeedbackProvider");
  return context;
}
