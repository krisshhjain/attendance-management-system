import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import EventAvailableRoundedIcon from "@mui/icons-material/EventAvailableRounded";
import FactCheckRoundedIcon from "@mui/icons-material/FactCheckRounded";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import NotificationsActiveRoundedIcon from "@mui/icons-material/NotificationsActiveRounded";
import WarningAmberRoundedIcon from "@mui/icons-material/WarningAmberRounded";
import {
  alpha,
  Badge,
  Box,
  Button,
  CircularProgress,
  Divider,
  Fade,
  IconButton,
  List,
  ListItemButton,
  ListItemAvatar,
  Popover,
  Stack,
  Typography,
  useTheme,
} from "@mui/material";
import { apiRequest } from "../../lib/api.js";

const notificationsQueryKey = ["notifications"];
const unreadNotificationsQueryKey = ["notifications", "unread"];

function formatNotificationDate(value) {
  if (!value) return "";
  return new Date(value).toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function isAttendanceNotification(notification) {
  return (
    String(notification.notification_type ?? "").toUpperCase() === "ATTENDANCE" ||
    notification.attendance_event != null
  );
}

function notificationType(notification) {
  return String(notification.notification_type ?? "SYSTEM").toUpperCase();
}

function notificationIcon(notification) {
  switch (notificationType(notification)) {
    case "ATTENDANCE":
      return <EventAvailableRoundedIcon fontSize="small" />;
    case "LEAVE":
    case "REGULARIZATION":
      return <FactCheckRoundedIcon fontSize="small" />;
    case "ABSENCE_ALERT":
      return <WarningAmberRoundedIcon fontSize="small" />;
    default:
      return <InfoOutlinedIcon fontSize="small" />;
  }
}

export function NotificationBell() {
  const queryClient = useQueryClient();
  const theme = useTheme();
  const [anchorEl, setAnchorEl] = useState(null);

  const notificationsQuery = useQuery({
    queryKey: notificationsQueryKey,
    queryFn: () => apiRequest("/notifications/"),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
  const unreadQuery = useQuery({
    queryKey: unreadNotificationsQueryKey,
    queryFn: () => apiRequest("/notifications/?unread=true"),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });

  const markReadMutation = useMutation({
    mutationFn: (notificationId) =>
      apiRequest(`/notifications/${notificationId}/read/`, {
        method: "PATCH",
        body: {},
      }),
    onMutate: async (notificationId) => {
      await Promise.all([
        queryClient.cancelQueries({ queryKey: notificationsQueryKey }),
        queryClient.cancelQueries({ queryKey: unreadNotificationsQueryKey }),
      ]);

      const previousNotifications = queryClient.getQueryData(notificationsQueryKey);
      const previousUnread = queryClient.getQueryData(unreadNotificationsQueryKey);

      queryClient.setQueryData(notificationsQueryKey, (current) =>
        Array.isArray(current)
          ? current.map((notification) =>
              notification.id === notificationId
                ? { ...notification, is_read: true }
                : notification,
            )
          : current,
      );
      queryClient.setQueryData(unreadNotificationsQueryKey, (current) =>
        Array.isArray(current)
          ? current.filter((notification) => notification.id !== notificationId)
          : current,
      );

      return { previousNotifications, previousUnread };
    },
    onError: (_error, _notificationId, context) => {
      queryClient.setQueryData(notificationsQueryKey, context?.previousNotifications);
      queryClient.setQueryData(unreadNotificationsQueryKey, context?.previousUnread);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: notificationsQueryKey });
      queryClient.invalidateQueries({ queryKey: unreadNotificationsQueryKey });
    },
  });

  const deleteAttendanceMutation = useMutation({
    mutationFn: async (notification) => {
      await apiRequest(`/notifications/${notification.id}/read/`, {
        method: "PATCH",
        body: {},
      });
      return apiRequest(`/notifications/${notification.id}/`, { method: "DELETE" });
    },
    onMutate: async (notification) => {
      await Promise.all([
        queryClient.cancelQueries({ queryKey: notificationsQueryKey }),
        queryClient.cancelQueries({ queryKey: unreadNotificationsQueryKey }),
      ]);

      const previousNotifications = queryClient.getQueryData(notificationsQueryKey);
      const previousUnread = queryClient.getQueryData(unreadNotificationsQueryKey);

      queryClient.setQueryData(notificationsQueryKey, (current) =>
        Array.isArray(current)
          ? current.filter((item) => item.id !== notification.id)
          : current,
      );
      queryClient.setQueryData(unreadNotificationsQueryKey, (current) =>
        Array.isArray(current)
          ? current.filter((item) => item.id !== notification.id)
          : current,
      );

      return { previousNotifications, previousUnread };
    },
    onError: (_error, _notification, context) => {
      queryClient.setQueryData(notificationsQueryKey, context?.previousNotifications);
      queryClient.setQueryData(unreadNotificationsQueryKey, context?.previousUnread);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: notificationsQueryKey });
      queryClient.invalidateQueries({ queryKey: unreadNotificationsQueryKey });
    },
  });

  const notifications = Array.isArray(notificationsQuery.data)
    ? notificationsQuery.data.slice(0, 6)
    : [];
  const unreadCount = Array.isArray(unreadQuery.data) ? unreadQuery.data.length : 0;
  const isOpen = Boolean(anchorEl);
  const hasError = notificationsQuery.isError || unreadQuery.isError;
  const isBusy = markReadMutation.isPending || deleteAttendanceMutation.isPending;

  const handleNotificationClick = (notification) => {
    if (isAttendanceNotification(notification)) {
      deleteAttendanceMutation.mutate(notification);
      return;
    }

    if (!notification.is_read) {
      markReadMutation.mutate(notification.id);
    }
  };

  const retryNotifications = () => {
    notificationsQuery.refetch();
    unreadQuery.refetch();
  };

  return (
    <>
      <IconButton
        aria-label={`Notifications${unreadCount ? `, ${unreadCount} unread` : ""}`}
        aria-controls={isOpen ? "notifications-popover" : undefined}
        aria-haspopup="true"
        onClick={(event) => setAnchorEl(event.currentTarget)}
        color="inherit"
        size="small"
        sx={{
          width: 40,
          height: 40,
          color: "text.secondary",
          transition: "background-color 160ms ease, color 160ms ease",
          "&:hover": { bgcolor: alpha(theme.palette.primary.main, 0.1), color: "primary.main" },
        }}
      >
        <Badge
          badgeContent={unreadCount}
          color="error"
          max={99}
          sx={{ "& .MuiBadge-badge": { fontWeight: 700, minWidth: 18, height: 18 } }}
        >
          <NotificationsActiveRoundedIcon fontSize="small" />
        </Badge>
      </IconButton>

      <Popover
        id="notifications-popover"
        open={isOpen}
        anchorEl={anchorEl}
        onClose={() => setAnchorEl(null)}
        TransitionComponent={Fade}
        transitionDuration={160}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        transformOrigin={{ vertical: "top", horizontal: "right" }}
        slotProps={{
          paper: {
            sx: {
              width: { xs: "calc(100vw - 24px)", sm: 390 },
              maxWidth: "calc(100vw - 24px)",
              overflow: "hidden",
              border: "1px solid",
              borderColor: "divider",
              borderRadius: 3,
              bgcolor: "background.paper",
              boxShadow: theme.shadows[10],
            },
          },
        }}
      >
        <Box sx={{ px: 2, py: 1.75, bgcolor: alpha(theme.palette.primary.main, 0.06) }}>
          <Stack direction="row" alignItems="center" justifyContent="space-between" gap={2}>
            <Box>
              <Typography variant="subtitle1" fontWeight={800}>
                Notifications
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {unreadCount ? `${unreadCount} unread` : "You are all caught up"}
              </Typography>
            </Box>
            <NotificationsActiveRoundedIcon color="primary" fontSize="small" />
          </Stack>
        </Box>
        <Divider />

        {notificationsQuery.isLoading || unreadQuery.isLoading ? (
          <Box sx={{ display: "flex", justifyContent: "center", py: 5 }}>
            <CircularProgress size={26} thickness={4} />
          </Box>
        ) : hasError ? (
          <Stack alignItems="center" spacing={1.25} sx={{ px: 2, py: 4 }}>
            <Typography variant="body2" color="error.main" align="center">
              Notifications could not be loaded. Please try again.
            </Typography>
            <Button size="small" onClick={retryNotifications} variant="outlined">
              Try again
            </Button>
          </Stack>
        ) : notifications.length === 0 ? (
          <Stack alignItems="center" spacing={1} sx={{ px: 2, py: 5 }}>
            <NotificationsActiveRoundedIcon sx={{ fontSize: 32, color: "text.disabled" }} />
            <Typography variant="body2" color="text.secondary" align="center">
              No notifications yet.
            </Typography>
          </Stack>
        ) : (
          <List disablePadding sx={{ maxHeight: 430, overflowY: "auto", p: 1 }}>
            {notifications.map((notification) => (
              <ListItemButton
                key={notification.id}
                onClick={() => handleNotificationClick(notification)}
                disabled={isBusy}
                sx={{
                  alignItems: "flex-start",
                  gap: 1,
                  px: 1.25,
                  py: 1.25,
                  mb: 0.5,
                  borderRadius: 2,
                  border: "1px solid",
                  borderColor: notification.is_read ? "transparent" : alpha(theme.palette.primary.main, 0.2),
                  bgcolor: notification.is_read ? "transparent" : alpha(theme.palette.primary.main, 0.07),
                  transition: "background-color 160ms ease, border-color 160ms ease",
                  "&:hover": { bgcolor: alpha(theme.palette.primary.main, 0.12) },
                }}
              >
                <ListItemAvatar sx={{ minWidth: 36, mt: 0.25 }}>
                  <Box
                    sx={{
                      width: 32,
                      height: 32,
                      display: "grid",
                      placeItems: "center",
                      borderRadius: "50%",
                      color: notification.is_read ? "text.secondary" : "primary.main",
                      bgcolor: notification.is_read
                        ? "action.hover"
                        : alpha(theme.palette.primary.main, 0.14),
                    }}
                  >
                    {notificationIcon(notification)}
                  </Box>
                </ListItemAvatar>
                <Box sx={{ minWidth: 0, flex: 1 }}>
                  <Typography
                    variant="body2"
                    fontWeight={notification.is_read ? 600 : 800}
                    noWrap
                  >
                    {notification.title}
                  </Typography>
                  <Typography
                    variant="caption"
                    color="primary.main"
                    sx={{ display: "block", mt: 0.2, fontWeight: 700, letterSpacing: 0.35 }}
                  >
                    {notificationType(notification).replaceAll("_", " ")}
                  </Typography>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ mt: 0.35, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}
                  >
                    {notification.message}
                  </Typography>
                  <Typography variant="caption" color="text.disabled" sx={{ display: "block", mt: 0.65 }}>
                    {formatNotificationDate(notification.created_at)}
                  </Typography>
                </Box>
              </ListItemButton>
            ))}
          </List>
        )}
      </Popover>
    </>
  );
}

export default NotificationBell;
