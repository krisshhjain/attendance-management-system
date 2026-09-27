import React from "react";
import PageHeader from "../components/common/PageHeader";
import Button from "../components/common/Button";
import Icon from "../components/common/Icon";
import EmptyState from "../components/common/EmptyState";
import { useApp } from "../context/AppContext";

export default function NotificationsPage() {
  const {
    notifications,
    markNotificationRead,
    markAllNotificationsRead,
    clearNotifications,
    setActivePage,
  } = useApp();

  const unreadCount = notifications.filter((n) => n.unread).length;

  return (
    <>
      <PageHeader
        title="Notifications"
        subtitle={`${unreadCount} unread updates across attendance, leave and requests.`}
        action={
          <div className="flex flex-wrap gap-2">
            {unreadCount > 0 && (
              <Button variant="secondary" onClick={markAllNotificationsRead}>
                Mark all as read
              </Button>
            )}
            {notifications.length > 0 && (
              <Button variant="ghost" onClick={clearNotifications}>
                Clear all
              </Button>
            )}
          </div>
        }
      />

      {notifications.length > 0 ? (
        <div className="space-y-3">
          {notifications.map((item) => (
            <div
              key={item.id}
              className={`notification-glass flex min-w-0 flex-wrap items-center gap-4 rounded-xl border p-4 shadow-xs transition ${
                item.unread
                  ? "border-indigo-200 bg-white/95"
                  : "border-slate-200/70 bg-white/60 opacity-80"
              }`}
            >
              <div
                className={`grid size-10 shrink-0 place-items-center rounded-lg ${
                  item.unread ? "bg-indigo-100 text-indigo-700" : "bg-slate-100 text-slate-500"
                }`}
              >
                <Icon name={item.icon} className="size-5" />
              </div>

              <div
                className="min-w-0 flex-1 cursor-pointer"
                onClick={() => {
                  if (item.unread) markNotificationRead(item.id);
                  if (item.link) setActivePage(item.link);
                }}
              >
                <div className="flex items-start gap-2">
                  <div
                    className={`break-words text-sm text-slate-900 ${
                      item.unread ? "font-bold" : "font-semibold"
                    }`}
                  >
                    {item.title}
                  </div>
                  {item.unread && (
                    <span className="mt-1.5 size-2 shrink-0 rounded-full bg-indigo-600" />
                  )}
                </div>
                <div
                  className={`mt-1 break-words text-sm ${
                    item.unread ? "text-slate-700" : "text-slate-500"
                  }`}
                >
                  {item.message}
                </div>
                <div className="mt-2 text-xs text-slate-400">{item.timeAgo}</div>
              </div>

              {item.unread && (
                <Button
                  variant="ghost"
                  className="shrink-0 text-indigo-600 hover:text-indigo-700"
                  onClick={() => markNotificationRead(item.id)}
                >
                  Mark read
                </Button>
              )}
            </div>
          ))}
        </div>
      ) : (
        <EmptyState
          title="You're all caught up"
          text="No notifications to show right now."
          icon="bell"
        />
      )}
    </>
  );
}
