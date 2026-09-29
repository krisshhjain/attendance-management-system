import { createFileRoute } from "@tanstack/react-router";
import { RequireAuth } from "../components/RequireAuth.jsx";
import { EmployeeAttendancePage } from "../components/employee-dashboard/EmployeeAttendancePage.jsx";

function AttendancePageContent() {
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
