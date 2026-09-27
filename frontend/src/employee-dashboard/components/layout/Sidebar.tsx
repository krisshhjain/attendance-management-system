import React from "react";
import Button from "../common/Button";
import Icon from "../common/Icon";
import Avatar from "../common/Avatar";
import { useApp } from "../../context/AppContext";
import type { Page, IconName } from "../../types";

const navGroups: {
  label: string;
  items: [Page, string, IconName][];
}[] = [
  {
    label: "WORKSPACE",
    items: [
      ["dashboard", "Dashboard", "grid"],
      ["attendance", "My Attendance", "calendar"],
      ["leave", "My Leave", "leave"],
      ["regularization", "Regularization", "refresh"],
      ["onduty", "On Duty", "briefcase"],
    ],
  },
  {
    label: "PERSONAL",
    items: [
      ["notifications", "Notifications", "bell"],
      ["profile", "My Profile", "user"],
    ],
  },
  {
    label: "SYSTEM",
    items: [["settings", "Settings", "settings"]],
  },
];

export default function Sidebar({
  open,
  close,
}: {
  open: boolean;
  close: () => void;
}) {
  const { user, activePage, setActivePage, unreadNotificationsCount } = useApp();

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-40 bg-slate-950/40 lg:hidden backdrop-blur-xs transition-opacity"
          onClick={close}
        />
      )}

      <aside
        className={`fixed inset-y-0 z-50 flex w-64 flex-col border-r border-slate-200 bg-white transition-[left] duration-200 ease-in-out lg:left-0 ${
          open ? "left-0" : "-left-64"
        }`}
      >
        <div className="flex h-16 items-center justify-between border-b border-slate-200 px-5">
          <div className="flex items-center gap-3">
            <div className="grid size-9 place-items-center rounded-lg bg-indigo-600 text-white shadow-sm">
              <Icon name="clock" className="size-5" />
            </div>
            <div>
              <div className="text-base font-semibold text-slate-900 tracking-tight">AttendPro</div>
              <div className="type-caption font-normal text-slate-500">Attendance Suite</div>
            </div>
          </div>
          <Button
            variant="ghost"
            className="px-2 lg:hidden text-slate-500 hover:text-slate-700"
            onClick={close}
            ariaLabel="Close sidebar menu"
          >
            <Icon name="close" />
          </Button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4">
          {navGroups.map((group) => (
            <div key={group.label} className="mb-5">
              <div className="type-caption mb-2 px-3 font-semibold uppercase tracking-wider text-slate-400">
                {group.label}
              </div>
              <div className="space-y-1">
                {group.items.map(([id, label, icon]) => {
                  const isActive = activePage === id;
                  return (
                    <Button
                      key={id}
                      variant="ghost"
                      onClick={() => {
                        setActivePage(id);
                        close();
                      }}
                      className={`relative w-full justify-start px-3 transition-colors ${
                        isActive
                          ? "bg-indigo-50 font-semibold text-indigo-700 hover:bg-indigo-50"
                          : "font-medium text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                      }`}
                    >
                      {isActive && (
                        <span className="absolute inset-y-2 left-0 w-1 rounded-r bg-indigo-600" />
                      )}
                      <Icon name={icon} className="size-4" />
                      <span>{label}</span>
                      {id === "notifications" && unreadNotificationsCount > 0 && (
                        <span className="ml-auto rounded-full bg-rose-500 px-1.5 py-0.5 text-xs font-semibold text-white">
                          {unreadNotificationsCount}
                        </span>
                      )}
                    </Button>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-slate-200 p-3">
          <Button
            variant="ghost"
            onClick={() => {
              setActivePage("profile");
              close();
            }}
            className="w-full justify-start px-2 py-2 hover:bg-slate-50"
          >
            <Avatar />
            <div className="min-w-0 text-left ml-2.5">
              <div className="truncate text-xs font-semibold text-slate-800">
                {user.name}
              </div>
              <div className="type-caption truncate font-normal text-slate-500">
                {user.designation}
              </div>
            </div>
            <Icon name="chevron" className="ml-auto size-4 text-slate-400" />
          </Button>
        </div>
      </aside>
    </>
  );
}
