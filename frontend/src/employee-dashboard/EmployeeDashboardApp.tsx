/**
 * EmployeeDashboardApp.tsx
 *
 * Self-contained shell for the Figma Employee Dashboard.
 * Rendered by /employee-dashboard TanStack route.
 * Wraps the AppProvider so it has its own isolated data context.
 * Does NOT replace or affect the existing Super Admin dashboard.
 */

import React, { useState, useMemo } from "react";
import { AppProvider, useApp } from "./context/AppContext";
import Sidebar from "./components/layout/Sidebar";
import Header from "./components/layout/Header";
import Toast from "./components/common/Toast";
import AttendanceModal, { type ModalType } from "./components/attendance/AttendanceModal";

// Pages
import DashboardPage from "./pages/DashboardPage";
import AttendancePage from "./pages/AttendancePage";
import LeavePage from "./pages/LeavePage";
import RegularizationPage from "./pages/RegularizationPage";
import OnDutyPage from "./pages/OnDutyPage";
import NotificationsPage from "./pages/NotificationsPage";
import ProfilePage from "./pages/ProfilePage";
import SettingsPage from "./pages/SettingsPage";

function AppContent() {
  const { activePage, setActivePage, toast, hideToast, settings } = useApp();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [attendanceModal, setAttendanceModal] = useState<ModalType | null>(null);

  const [regularizationDate, setRegularizationDate] = useState<string>();
  const [regularizationCheckIn, setRegularizationCheckIn] = useState<string>();

  const handleRegularize = (dateIso: string, checkIn?: string) => {
    setRegularizationDate(dateIso);
    setRegularizationCheckIn(checkIn);
    setActivePage("regularization");
  };

  const pageContent = useMemo(() => {
    switch (activePage) {
      case "dashboard":
        return (
          <DashboardPage
            openModal={setAttendanceModal}
            onRegularize={handleRegularize}
          />
        );
      case "attendance":
        return <AttendancePage onRegularize={handleRegularize} />;
      case "leave":
        return <LeavePage />;
      case "regularization":
        return (
          <RegularizationPage
            initialDate={regularizationDate}
            initialCheckIn={regularizationCheckIn}
          />
        );
      case "onduty":
        return <OnDutyPage />;
      case "notifications":
        return <NotificationsPage />;
      case "profile":
        return <ProfilePage />;
      case "settings":
        return <SettingsPage />;
      default:
        return (
          <DashboardPage
            openModal={setAttendanceModal}
            onRegularize={handleRegularize}
          />
        );
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activePage, regularizationDate, regularizationCheckIn]);

  return (
    <div
      className={`min-h-screen w-full min-w-0 max-w-full overflow-x-hidden bg-slate-50 text-slate-800 transition-colors ${
        settings.theme === "dark" ? "dark" : ""
      }`}
    >
      <Sidebar open={sidebarOpen} close={() => setSidebarOpen(false)} />

      <div className="w-full min-w-0 max-w-full overflow-x-hidden lg:pl-64">
        <Header openMenu={() => setSidebarOpen(true)} />
        <main className="mx-auto w-full min-w-0 max-w-screen-2xl overflow-x-hidden p-4 sm:p-6 lg:p-8">
          {pageContent}
        </main>
      </div>

      {attendanceModal && (
        <AttendanceModal
          modal={attendanceModal}
          close={() => setAttendanceModal(null)}
        />
      )}

      {toast && <Toast text={toast} close={hideToast} />}
    </div>
  );
}

export default function EmployeeDashboardApp() {
  return (
    <AppProvider>
      <AppContent />
    </AppProvider>
  );
}
