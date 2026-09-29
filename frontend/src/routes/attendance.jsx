import { createFileRoute } from "@tanstack/react-router";
import { RequireAuth } from "../components/RequireAuth.jsx";
import { EmployeeAttendancePage } from "../components/employee-dashboard/EmployeeAttendancePage.jsx";
import { AdminAttendancePage } from "../components/admin/AdminAttendancePage.jsx";
import { useAuth } from "../lib/auth.jsx";

function AttendancePageContent() {
  const { loginType } = useAuth();
  if (loginType === "admin" || loginType === "systemadmin") {
    return <AdminAttendancePage allowReset={loginType === "admin"} />;
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
