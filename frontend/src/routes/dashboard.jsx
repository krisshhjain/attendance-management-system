import { createFileRoute } from "@tanstack/react-router";
import { RequireAuth } from "../components/RequireAuth.jsx";
import { Box, Typography, Button } from "@mui/material";
import { useAuth } from "../lib/auth.jsx";
import { StatCard } from "../components/dashboard/StatCard.jsx";
import { AttendanceChart } from "../components/dashboard/AttendanceChart.jsx";
import { EmployeeTable } from "../components/dashboard/EmployeeTable.jsx";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../lib/api.js";
import { getAdminAttendance } from "../lib/attendance.js";
import PeopleIcon from "@mui/icons-material/People";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import DoneAllIcon from "@mui/icons-material/DoneAll";
import PersonIcon from "@mui/icons-material/Person";
import { OrganizationScopeFilters } from "../components/dashboard/OrganizationScopeFilters.jsx";
import { filterScopedRecords, useOrganizationScope } from "../lib/organizationScope.jsx";

function SuperAdminDashboard() {
  const { user, loginType } = useAuth();
  const { selectedScope } = useOrganizationScope();
  const { data } = useQuery({
    queryKey: ["adminDashboard"],
    queryFn: () => apiRequest("/admin/dashboard/"),
  });
  const { data: employees } = useQuery({
    queryKey: ["employees"],
    queryFn: () => apiRequest("/admin/employees/list/"),
  });
  const { data: todayAttendance = [] } = useQuery({
    queryKey: ["adminAttendance", new Date().toLocaleDateString("en-CA")],
    queryFn: () => getAdminAttendance(new Date().toLocaleDateString("en-CA")),
  });
  const employeeRecords = employees || [];
  const scopedEmployees = filterScopedRecords(employeeRecords, selectedScope);
  const scopedAttendance = filterScopedRecords(Array.isArray(todayAttendance) ? todayAttendance : todayAttendance?.results, selectedScope);
  const hasScopedEmployeeData = Array.isArray(employees);
  const hasScopedAttendanceData = Array.isArray(scopedAttendance);
  const attendanceSummary = hasScopedAttendanceData ? {
    present_today: scopedAttendance.filter((record) => record.status === "PRESENT").length,
    checked_in_today: scopedAttendance.filter((record) => record.check_in && !record.check_out).length,
    completed_today: scopedAttendance.filter((record) => record.check_in && record.check_out).length,
  } : {};
  const scopedData = data ? {
    ...data,
    ...(hasScopedEmployeeData ? {
      total_employees: scopedEmployees.length,
      active_employees: scopedEmployees.filter((employee) => employee.is_active).length,
    } : {}),
    ...(hasScopedAttendanceData ? attendanceSummary : {}),
    employees: filterScopedRecords(data.employees, selectedScope),
    attendance: filterScopedRecords(data.attendance, selectedScope),
    leave_requests: filterScopedRecords(data.leave_requests, selectedScope),
  } : data;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1 }}>
        <Typography variant="h5" sx={{ fontWeight: 700, letterSpacing: "-0.5px" }}>
          Dashboard Overview
        </Typography>
      </Box>
      {loginType === "systemadmin" && <OrganizationScopeFilters user={user} employees={employeeRecords} />}
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", md: "repeat(5, 1fr)" }, gap: 2 }}>
        <StatCard title="Total Employees" value={scopedData?.total_employees} icon={<PeopleIcon />} />
        <StatCard title="Active Employees" value={scopedData?.active_employees} icon={<PersonIcon />} />
        <StatCard title="Present Today" value={scopedData?.present_today} icon={<CheckCircleOutlineIcon />} subtitle="Checked out" subtitleColor="success.main" />
        <StatCard title="Checked In" value={scopedData?.checked_in_today} icon={<AccessTimeIcon />} subtitle="Currently active" subtitleColor="primary.main" />
        <StatCard title="Completed" value={scopedData?.completed_today} icon={<DoneAllIcon />} />
      </Box>
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "350px 1fr" }, gap: 3 }}>
        <AttendanceChart data={scopedData} />
        <EmployeeTable scope={selectedScope} />
      </Box>
    </Box>
  );
}

import { WelcomeHeader } from "../components/employee-dashboard/WelcomeHeader.jsx";
import { TodayAttendanceWidget } from "../components/employee-dashboard/TodayAttendanceWidget.jsx";
import { SummaryCards } from "../components/employee-dashboard/SummaryCards.jsx";
import { RecentAttendance } from "../components/employee-dashboard/RecentAttendance.jsx";
import { QuickActions } from "../components/employee-dashboard/QuickActions.jsx";
import { getToday } from "../lib/attendance.js";

function EmployeeDashboard() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["todayAttendance"],
    queryFn: () => getToday(),
  });

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <WelcomeHeader />
      
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "1fr 2fr" }, gap: 3 }}>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
          <TodayAttendanceWidget data={data} loading={isLoading} loadError={isError} reloadData={refetch} />
          <QuickActions />
        </Box>
        <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
          <SummaryCards data={data} />
          <RecentAttendance />
        </Box>
      </Box>
    </Box>
  );
}

function DashboardComponent() {
  const { user, loginType } = useAuth();

  if (loginType === "systemadmin") {
    return <SuperAdminDashboard />;
  }

  if (loginType === "systemadmin" || loginType === "admin") {
    if (user?.is_superuser) {
      return <SuperAdminDashboard />;
    }
    if (user?.is_staff) {
      return (
        <Box sx={{ p: 4, textAlign: "center", bgcolor: "white", borderRadius: 4, border: "1px solid", borderColor: "divider" }}>
          <Typography variant="h5" fontWeight={600} gutterBottom>Admin Dashboard</Typography>
          <Typography color="text.secondary">This view is coming soon. Please check back later.</Typography>
        </Box>
      );
    }
  }
  
  return <EmployeeDashboard />;
}

export const Route = createFileRoute("/dashboard")({
  head: () => ({
    meta: [
      { title: "Dashboard — AttendPro" },
      { name: "description", content: "Overview of your daily attendance and recent activity." },
      { property: "og:title", content: "Dashboard — AttendPro" },
      { property: "og:description", content: "Overview of your daily attendance and recent activity." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: () => (
    <RequireAuth>
      <DashboardComponent />
    </RequireAuth>
  ),
});
