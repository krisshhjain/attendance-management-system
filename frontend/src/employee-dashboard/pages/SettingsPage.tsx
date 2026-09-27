import React, { useState } from "react";
import PageHeader from "../components/common/PageHeader";
import Card from "../components/common/Card";
import SectionTitle from "../components/common/SectionTitle";
import Button from "../components/common/Button";
import Toggle from "../components/common/Toggle";
import Field from "../components/common/Field";
import Icon from "../components/common/Icon";
import { useApp } from "../context/AppContext";

export default function SettingsPage() {
  const { user, settings, updateSettings, updateProfile, setTheme, resetDemoData } = useApp();

  const [email, setEmail] = useState(settings.emailNotifications);
  const [push, setPush] = useState(settings.pushNotifications);
  const [reminders, setReminders] = useState(settings.attendanceReminders);
  const [language, setLanguage] = useState(settings.language || "English");
  const [timezone, setTimezone] = useState(settings.timezone || "India Standard Time");
  const [displayName, setDisplayName] = useState(user.name);

  // Password modal simulation
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordToast, setPasswordToast] = useState("");

  const handleSaveNotifications = async (e: boolean, p: boolean, r: boolean) => {
    setEmail(e);
    setPush(p);
    setReminders(r);
    await updateSettings({
      emailNotifications: e,
      pushNotifications: p,
      attendanceReminders: r,
    });
  };

  const handleSaveAccountPreferences = async () => {
    await Promise.all([
      updateProfile({ name: displayName }),
      updateSettings({ language, timezone }),
    ]);
  };

  const handlePasswordChange = (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword.length < 6) {
      setPasswordToast("New password must be at least 6 characters.");
      return;
    }
    setShowPasswordModal(false);
    setOldPassword("");
    setNewPassword("");
    setPasswordToast("");
    alert("Password updated successfully.");
  };

  return (
    <>
      <PageHeader
        title="Settings"
        subtitle="Manage your account preferences, notifications and security."
      />

      <div className="grid gap-5 xl:grid-cols-[1.4fr_1fr]">
        <div className="space-y-5">
          {/* Notifications Card */}
          <Card>
            <SectionTitle
              title="Notifications"
              subtitle="Choose how you receive updates and alerts"
            />
            <div className="divide-y divide-slate-100">
              <div className="flex items-center justify-between gap-4 p-5">
                <div>
                  <div className="text-sm font-semibold text-slate-700">
                    Email notifications
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    Receive approval and request updates by email
                  </div>
                </div>
                <Toggle
                  checked={email}
                  setChecked={(val) => handleSaveNotifications(val, push, reminders)}
                  label="Email notifications"
                />
              </div>

              <div className="flex items-center justify-between gap-4 p-5">
                <div>
                  <div className="text-sm font-semibold text-slate-700">
                    Push notifications
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    Receive updates directly in the AttendPro app
                  </div>
                </div>
                <Toggle
                  checked={push}
                  setChecked={(val) => handleSaveNotifications(email, val, reminders)}
                  label="Push notifications"
                />
              </div>

              <div className="flex items-center justify-between gap-4 p-5">
                <div>
                  <div className="text-sm font-semibold text-slate-700">
                    Attendance reminders
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    Remind me to check in and check out on workdays
                  </div>
                </div>
                <Toggle
                  checked={reminders}
                  setChecked={(val) => handleSaveNotifications(email, push, val)}
                  label="Attendance reminders"
                />
              </div>
            </div>
          </Card>

          {/* Appearance Card */}
          <Card>
            <SectionTitle
              title="Appearance"
              subtitle="Choose how AttendPro looks on this device"
            />
            <div className="grid gap-4 p-5 sm:grid-cols-2">
              <Field
                label="Theme"
                value={settings.theme === "dark" ? "Dark" : "Light"}
                onChange={(val) => setTheme(val.toLowerCase() as "light" | "dark")}
                options={["Light", "Dark"]}
              />
              <Field
                label="Language"
                value={language}
                onChange={setLanguage}
                options={["English", "Hindi", "Spanish", "French"]}
              />
            </div>

            <div className="grid grid-cols-2 gap-3 border-t border-slate-200 p-5">
              <Button
                variant={settings.theme === "light" ? "primary" : "secondary"}
                onClick={() => setTheme("light")}
              >
                <Icon name="sun" className="size-4" />
                Light Theme
              </Button>
              <Button
                variant={settings.theme === "dark" ? "primary" : "secondary"}
                onClick={() => setTheme("dark")}
              >
                <Icon name="moon" className="size-4" />
                Dark Theme
              </Button>
            </div>
          </Card>
        </div>

        <div className="space-y-5">
          {/* Account Card */}
          <Card>
            <SectionTitle title="Account Preferences" />
            <div className="space-y-4 p-5">
              <Field
                label="Display name"
                value={displayName}
                onChange={setDisplayName}
              />
              <Field
                label="Time zone"
                value={timezone}
                onChange={setTimezone}
                options={[
                  "India Standard Time (UTC+05:30)",
                  "Coordinated Universal Time (UTC)",
                  "Eastern Standard Time (UTC-05:00)",
                  "Pacific Standard Time (UTC-08:00)",
                ]}
              />
              <Button onClick={handleSaveAccountPreferences}>
                Save account preferences
              </Button>
            </div>
          </Card>

          {/* Security Card */}
          <Card>
            <SectionTitle title="Security & Authentication" />
            <div className="p-5">
              <div className="mb-4 flex items-start gap-3">
                <div className="rounded-lg bg-emerald-50 p-2 text-emerald-700">
                  <Icon name="shield" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-slate-700">
                    Password Protected
                  </div>
                  <div className="mt-1 text-xs text-slate-500">
                    2-Factor Authentication active
                  </div>
                </div>
              </div>
              <Button variant="secondary" onClick={() => setShowPasswordModal(true)}>
                Change Password
              </Button>
            </div>
          </Card>

          {/* Demo Data Management */}
          <Card>
            <SectionTitle
              title="Demo State Management"
              subtitle="Reset or restore dynamic demo data"
            />
            <div className="p-5 space-y-3">
              <p className="text-xs text-slate-500">
                You can reset your attendance, leave, and regularization history back to
                default demo records calculated relative to today.
              </p>
              <Button variant="danger" onClick={resetDemoData}>
                Reset All Demo Data
              </Button>
            </div>
          </Card>
        </div>
      </div>

      {/* Password Modal */}
      {showPasswordModal && (
        <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/45 p-4 backdrop-blur-xs">
          <Card className="w-full max-w-sm overflow-hidden shadow-2xl">
            <div className="flex items-center justify-between border-b border-slate-200 px-5 py-4">
              <div className="text-base font-bold text-slate-900">Change Password</div>
              <Button
                variant="ghost"
                className="px-2"
                onClick={() => setShowPasswordModal(false)}
              >
                <Icon name="close" />
              </Button>
            </div>

            <form onSubmit={handlePasswordChange} className="p-5 space-y-4">
              <Field
                label="Current Password"
                type="password"
                value={oldPassword}
                onChange={setOldPassword}
                placeholder="Enter current password"
                required
              />
              <Field
                label="New Password"
                type="password"
                value={newPassword}
                onChange={setNewPassword}
                placeholder="Enter new password"
                required
              />
              {passwordToast && (
                <div className="text-xs text-rose-600 font-medium">{passwordToast}</div>
              )}
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="secondary" onClick={() => setShowPasswordModal(false)}>
                  Cancel
                </Button>
                <Button type="submit">Update Password</Button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </>
  );
}
