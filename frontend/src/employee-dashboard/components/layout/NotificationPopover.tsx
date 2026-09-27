import React from "react";
import Card from "../common/Card";
import Button from "../common/Button";
import Icon from "../common/Icon";
import { useApp } from "../../context/AppContext";

export default function NotificationPopover({
  close,
  viewAll,
}: {
  close: () => void;
  viewAll: () => void;
}) {
  const { notifications, markNotificationRead, markAllNotificationsRead } = useApp();
  const unreadItems = notifications.filter((n) => n.unread);

  return (
    <>
      <div className="fixed inset-0 z-40" onClick={close} />
      <Card className="fixed left-3 right-3 top-16 z-50 overflow-hidden shadow-xl sm:absolute sm:left-auto sm:right-0 sm:top-12 sm:w-96">
        <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
          <div>
            <div className="text-sm font-bold text-slate-900">Notifications</div>
            <div className="text-xs text-slate-500">{unreadItems.length} unread updates</div>
          </div>
          {unreadItems.length > 0 && (
            <Button variant="ghost" className="min-h-8 px-2" onClick={markAllNotificationsRead}>
              Mark all read
            </Button>
          )}
        </div>

        {unreadItems.length > 0 ? (
          <div className="max-h-80 divide-y divide-slate-100 overflow-y-auto">
            {unreadItems.map((item) => (
              <div
                key={item.id}
                className="flex gap-3 bg-indigo-50/50 p-4 transition hover:bg-indigo-50/80 cursor-pointer"
                onClick={() => {
                  markNotificationRead(item.id);
                  if (item.link) {
                    viewAll();
                  }
                }}
              >
                <div className="grid size-9 shrink-0 place-items-center rounded-lg bg-white text-indigo-600 shadow-sm">
                  <Icon name={item.icon} className="size-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <div className="truncate text-sm font-bold text-slate-800">{item.title}</div>
                    <span className="size-2 shrink-0 rounded-full bg-indigo-600" />
                  </div>
                  <div className="mt-1 text-xs leading-5 text-slate-600">{item.message}</div>
                  <div className="mt-1 text-xs text-slate-400">{item.timeAgo}</div>
                </div>
                <Button
                  variant="ghost"
                  className="min-h-8 self-start px-1 text-slate-400 hover:text-slate-600"
                  onClick={(e) => {
                    e.stopPropagation();
                    markNotificationRead(item.id);
                  }}
                  ariaLabel="Mark notification as read"
                >
                  <Icon name="close" className="size-3" />
                </Button>
              </div>
            ))}
          </div>
        ) : (
          <div className="p-8 text-center">
            <div className="text-sm font-semibold text-slate-700">You're all caught up</div>
            <div className="mt-1 text-xs text-slate-500">No unread notifications.</div>
          </div>
        )}

        <div className="border-t border-slate-200 p-2">
          <Button variant="ghost" className="w-full text-indigo-600" onClick={viewAll}>
            View all notifications <Icon name="chevron" className="size-4" />
          </Button>
        </div>
      </Card>
    </>
  );
}
