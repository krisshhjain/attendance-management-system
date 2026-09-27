import React, { useState } from "react";
import Button from "../common/Button";
import Icon from "../common/Icon";
import Avatar from "../common/Avatar";
import NotificationPopover from "./NotificationPopover";
import { useApp } from "../../context/AppContext";

export default function Header({ openMenu }: { openMenu: () => void }) {
  const { user, settings, setTheme, activePage, setActivePage, unreadNotificationsCount } = useApp();
  const [notificationsOpen, setNotificationsOpen] = useState(false);

  const toggleTheme = () => {
    setTheme(settings.theme === "light" ? "dark" : "light");
  };

  const firstName = user.name ? user.name.split(" ")[0] : "User";

  const pageNames: Record<string, string> = {
    dashboard: "Self Service",
    attendance: "My Attendance",
    leave: "My Leave",
    regularization: "Regularization",
    onduty: "On Duty",
    notifications: "Notifications",
    profile: "My Profile",
    settings: "Settings",
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200 bg-white px-4 sm:px-6 lg:px-8">
      <Button
        variant="ghost"
        className="px-2 lg:hidden"
        onClick={openMenu}
        ariaLabel="Open navigation menu"
      >
        <Icon name="menu" />
      </Button>

      <div className="type-meta hidden items-center gap-2 font-normal text-slate-500 sm:flex">
        <span>Employee Workspace</span>
        <span>/</span>
        <span className="font-medium text-slate-700">{pageNames[activePage] || "Self Service"}</span>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <Button
          variant="ghost"
          className="px-2"
          onClick={toggleTheme}
          ariaLabel={`Switch to ${settings.theme === "light" ? "dark" : "light"} theme`}
        >
          <Icon name={settings.theme === "light" ? "moon" : "sun"} />
        </Button>

        <div className="relative">
          <Button
            variant="ghost"
            className="relative px-2"
            onClick={() => setNotificationsOpen(!notificationsOpen)}
            ariaLabel="View notifications"
          >
            <Icon name="bell" />
            {unreadNotificationsCount > 0 && (
              <span className="type-caption absolute right-0.5 top-0.5 grid min-w-4 place-items-center rounded-full bg-rose-500 px-1 py-0.5 font-semibold text-white ring-2 ring-white">
                {unreadNotificationsCount}
              </span>
            )}
          </Button>

          {notificationsOpen && (
            <NotificationPopover
              close={() => setNotificationsOpen(false)}
              viewAll={() => {
                setNotificationsOpen(false);
                setActivePage("notifications");
              }}
            />
          )}
        </div>

        <Button
          variant="ghost"
          className="px-2"
          onClick={() => setActivePage("profile")}
          ariaLabel="Go to profile"
        >
          <Avatar />
          <span className="hidden text-xs font-medium text-slate-700 sm:inline ml-2">
            {firstName}
          </span>
        </Button>
      </div>
    </header>
  );
}
