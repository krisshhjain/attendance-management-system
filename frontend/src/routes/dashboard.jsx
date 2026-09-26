import { useState } from "react";
import { Dialog, DialogTitle, DialogContent, List, ListItem, ListItemAvatar, Avatar, ListItemText, IconButton, Divider, Box, Typography, Button } from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import { useNavigate, createFileRoute } from "@tanstack/react-router";
import { RequireAuth } from "../components/RequireAuth.jsx";
import { useAuth } from "../lib/auth.jsx";
import { StatCard } from "../components/dashboard/StatCard.jsx";
import { AttendanceChart } from "../components/dashboard/AttendanceChart.jsx";
import { WeeklyTrendChart } from "../components/dashboard/WeeklyTrendChart.jsx";
import { UpcomingLeaves } from "../components/dashboard/UpcomingLeaves.jsx";
import { LatestAttendanceTable } from "../components/dashboard/LatestAttendanceTable.jsx";
import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "../lib/api.js";
import PeopleIcon from "@mui/icons-material/People";
import CheckCircleOutlineIcon from "@mui/icons-material/CheckCircleOutline";
import PersonOffOutlinedIcon from "@mui/icons-material/PersonOffOutlined";
import BusinessCenterOutlinedIcon from "@mui/icons-material/BusinessCenterOutlined";
import { OrganizationScopeFilters } from "../components/dashboard/OrganizationScopeFilters.jsx";
import { filterScopedRecords, useOrganizationScope } from "../lib/organizationScope.jsx";

function SuperAdminDashboard() {
  const { user, loginType } = useAuth();
  const { selectedScope } = useOrganizationScope();
  const navigate = useNavigate();
  const [modalState, setModalState] = useState({ open: false, title: "", type: null });

  const { data } = useQuery({
    queryKey: ["adminDashboard"],
    queryFn: () => apiRequest("/admin/dashboard/"),
  });
  const { data: employees } = useQuery({
    queryKey: ["employees"],
    queryFn: () => apiRequest("/admin/employees/list/"),
  });

  const employeeRecords = employees || [];
  const scopedEmployees = filterScopedRecords(employeeRecords, selectedScope);
  const scopedAttendance = filterScopedRecords(data?.attendance, selectedScope);
  const hasScopedEmployeeData = Array.isArray(employees);
  const hasScopedAttendanceData = Array.isArray(scopedAttendance);

  const presentRecords = scopedAttendance?.filter((record) => record.status === "PRESENT" || record.status === "INCOMPLETE") || [];
  const leaveRecords = scopedAttendance?.filter((record) => record.status === "LEAVE") || [];
  
  const presentEmails = new Set(presentRecords.map(r => r.employee));
  const leaveEmails = new Set(leaveRecords.map(r => r.employee));

  const attendanceSummary = hasScopedAttendanceData ? {
    present_today: presentRecords.length,
    checked_in_today: scopedAttendance.filter((record) => record.check_in && !record.check_out).length,
    completed_today: scopedAttendance.filter((record) => record.check_in && record.check_out).length,
    on_leave: leaveRecords.length,
  } : {};

  const scopedData = data ? {
    ...data,
    ...(hasScopedEmployeeData ? {
      total_employees: scopedEmployees.length,
      active_employees: scopedEmployees.filter((employee) => employee.is_active).length,
    } : {}),
    ...(hasScopedAttendanceData ? attendanceSummary : {}),
  } : data;

  const totalEmployees = scopedData?.total_employees || 0;
  const presentToday = scopedData?.present_today || 0;
  const onLeave = scopedData?.on_leave || 0;
  
  const isWorkingDay = scopedData?.is_working_day ?? true;
  const absentToday = isWorkingDay ? Math.max(0, totalEmployees - presentToday - onLeave) : 0;

  const getEmployeeName = (emp) => {
    if (typeof emp === 'string') return emp;
    if (emp?.first_name) return `${emp.first_name} ${emp.last_name || ''}`.trim();
    if (emp?.user?.first_name) return `${emp.user.first_name} ${emp.user.last_name || ''}`.trim();
    return emp?.user?.email || emp?.email || 'Unknown';
  };

  const getUserList = (type) => {
    if (type === "PRESENT") {
      return presentRecords.map(r => ({
        name: r.employee_name || r.employee,
        email: r.employee,
        dept: r.section || "---"
      }));
    } else if (type === "LEAVE") {
      return leaveRecords.map(r => ({
        name: r.employee_name || r.employee,
        email: r.employee,
        dept: r.section || "---"
      }));
    } else if (type === "ABSENT") {
      return scopedEmployees
        .filter(e => !presentEmails.has(e.user?.email) && !leaveEmails.has(e.user?.email))
        .map(e => ({
          name: getEmployeeName(e),
          email: e.user?.email,
          dept: e.section || "---"
        }));
    }
    return [];
  };

  const handleOpenModal = (title, type) => {
    setModalState({ open: true, title, type });
  };

  return (
    <Box sx={{ display: "flex", flexDirection: "column", gap: 3 }}>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 0 }}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 700, letterSpacing: "-0.5px", color: "#0f172a" }}>
            Overview
          </Typography>
          <Typography variant="body2" sx={{ color: "#64748b", mt: 0.5 }}>
            Here's what's happening today
          </Typography>
        </Box>
      </Box>
      
      {loginType === "systemadmin" && <OrganizationScopeFilters user={user} employees={employeeRecords} />}
      
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", md: "repeat(4, 1fr)" }, gap: 3 }}>
        <StatCard title="Total Employees" value={totalEmployees} icon={<PeopleIcon fontSize="small" />} colorClass="primary" subtitle="Across all departments" onClick={() => navigate({ to: "/employees" })} />
        <StatCard title="Present Today" value={presentToday} icon={<CheckCircleOutlineIcon fontSize="small" />} colorClass="success" subtitle="Currently checked in" onClick={() => handleOpenModal("Present Today", "PRESENT")} />
        <StatCard title="Absent Today" value={absentToday} icon={<PersonOffOutlinedIcon fontSize="small" />} colorClass="error" subtitle="Not arrived yet" onClick={() => handleOpenModal("Absent Today", "ABSENT")} />
        <StatCard title="On Leave" value={onLeave} icon={<BusinessCenterOutlinedIcon fontSize="small" />} colorClass="warning" subtitle="Approved leaves today" onClick={() => handleOpenModal("On Leave Today", "LEAVE")} />
      </Box>
      
      <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", lg: "1fr 2fr 1fr" }, gap: 3 }}>
        <AttendanceChart data={scopedData} />
        <WeeklyTrendChart />
        <UpcomingLeaves />
      </Box>

      <Box sx={{ mt: 1 }}>
        <LatestAttendanceTable records={(scopedAttendance || []).map(record => {
          const emp = scopedEmployees.find(e => e.user?.email === record.employee || e.email === record.employee || e.id === record.employee);
          return {
            ...record,
            employee_name: emp ? getEmployeeName(emp) : (record.employee_name || record.employee)
          };
        })} />
      </Box>

      <Dialog 
        open={modalState.open} 
        onClose={() => setModalState({ ...modalState, open: false })}
        maxWidth="sm"
        fullWidth
        PaperProps={{ sx: { borderRadius: "16px", boxShadow: "0 20px 25px -5px rgb(0 0 0 / 0.1)" } }}
      >
        <DialogTitle sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", pb: 1 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, color: "#0f172a" }}>{modalState.title}</Typography>
          <IconButton onClick={() => setModalState({ ...modalState, open: false })} size="small" sx={{ color: "#64748b" }}>
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <Divider />
        <DialogContent sx={{ p: 0 }}>
          <List sx={{ pt: 0, pb: 0, maxHeight: "60vh", overflow: "auto" }}>
            {getUserList(modalState.type).length === 0 ? (
              <Box sx={{ p: 4, textAlign: "center", color: "#64748b" }}>
                <Typography variant="body2">No employees found in this category.</Typography>
              </Box>
            ) : (
              getUserList(modalState.type).map((u, i) => (
                <ListItem key={i} divider={i < getUserList(modalState.type).length - 1} sx={{ px: 3, py: 1.5 }}>
                  <ListItemAvatar>
                    <Avatar sx={{ bgcolor: "primary.light", color: "primary.main", fontWeight: 600, width: 40, height: 40 }}>
                      {u.name.charAt(0).toUpperCase()}
                    </Avatar>
                  </ListItemAvatar>
                  <ListItemText 
                    primary={<Typography sx={{ fontWeight: 600, color: "#1e293b", fontSize: "14px" }}>{u.name}</Typography>}
                    secondary={<Typography sx={{ fontSize: "13px", color: "#64748b" }}>{u.dept}</Typography>}
                  />
                </ListItem>
              ))
            )}
          </List>
        </DialogContent>
      </Dialog>
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
