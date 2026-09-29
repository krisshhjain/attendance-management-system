import { createFileRoute } from "@tanstack/react-router";
import { RequireAuth } from "../components/RequireAuth.jsx";
import { EmployeeAttendancePage } from "../components/employee-dashboard/EmployeeAttendancePage.jsx";
import { AdminAttendancePage } from "../components/admin/AdminAttendancePage.jsx";
import { useAuth } from "../lib/auth.jsx";

function AttendancePageContent() {
  const { user, loginType } = useAuth();

  const isSystemAdmin = loginType === "systemadmin";
  const isSuperAdmin = loginType === "admin" || user?.is_superuser;
  const isManager = user?.is_staff;

  if (isSystemAdmin || isSuperAdmin) {
    return <AdminAttendancePage allowReset={true} />;
  }

  if (isManager) {
    return <AdminAttendancePage allowReset={false} />;
  }

  return <EmployeeAttendancePage />;
}

export const Route = createFileRoute("/attendance")({
  head: () => ({ meta: [{ title: "My Attendance — AttendPro" }] }),
  component: () => (
    <RequireAuth>
      <AttendancePageContent />
    </RequireAuth>
  ),
});
