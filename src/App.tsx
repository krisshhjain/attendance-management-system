import { useState, useRef, useEffect, type ReactNode } from "react";

type IconName =
  | "grid" | "users" | "manager" | "calendar" | "leave" | "report"
  | "building" | "settings" | "logout" | "search" | "bell" | "menu"
  | "close" | "plus" | "clock" | "userCheck" | "userX" | "briefcase"
  | "arrowUp" | "arrowRight" | "chevronDown";

const iconPaths: Record<IconName, ReactNode> = {
  grid: (<><rect x="3" y="3" width="7" height="7" rx="2" /><rect x="14" y="3" width="7" height="7" rx="2" /><rect x="3" y="14" width="7" height="7" rx="2" /><rect x="14" y="14" width="7" height="7" rx="2" /></>),
  users: (<><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" /></>),
  manager: (<><circle cx="12" cy="8" r="4" /><path d="M5.5 21a6.5 6.5 0 0 1 13 0M9 14.75l3 3 3-3" /></>),
  calendar: (<><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 11h18M8 15h.01M12 15h.01M16 15h.01" /></>),
  leave: (<><path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 18 2 18 2c1 5.5-.7 12.2-7 14.5" /><path d="M2 21c2-5 5.5-8.5 10-11" /></>),
  report: (<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><path d="M14 2v6h6M8 17v-3M12 17v-6M16 17v-2" /></>),
  building: (<><path d="M3 21h18M6 21V4h9v17M15 9h3v12M9 8h2M9 12h2M9 16h2" /></>),
  settings: (<><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6h.08A1.65 1.65 0 0 0 10 3.09V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9v.08A1.65 1.65 0 0 0 20.91 10H21a2 2 0 1 1 0 4h-.09A1.65 1.65 0 0 0 19.4 15z" /></>),
  logout: (<><path d="M10 17l5-5-5-5M15 12H3M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" /></>),
  search: (<><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>),
  bell: (<><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M13.7 21h-3.4" /></>),
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  close: <path d="M18 6 6 18M6 6l12 12" />,
  plus: <path d="M12 5v14M5 12h14" />,
  clock: (<><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>),
  userCheck: (<><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M8.5 11a4 4 0 1 0 0-8M17 11l2 2 4-4" /></>),
  userX: (<><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M8.5 11a4 4 0 1 0 0-8M18 8l5 5M23 8l-5 5" /></>),
  briefcase: (<><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18M10 12v2h4v-2" /></>),
  arrowUp: <path d="m18 15-6-6-6 6" />,
  arrowRight: <path d="m9 18 6-6-6-6" />,
  chevronDown: <path d="m6 9 6 6 6-6" />,
};

function Icon({ name, className = "h-5 w-5" }: { name: IconName; className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {iconPaths[name]}
    </svg>
  );
}

const navItems: { name: string; icon: IconName }[] = [
  { name: "Dashboard", icon: "grid" },
  { name: "Employees", icon: "users" },
  { name: "Managers", icon: "manager" },
  { name: "Attendance", icon: "calendar" },
  { name: "Leave Management", icon: "leave" },
  { name: "Reports", icon: "report" },
  { name: "Departments", icon: "building" },
  { name: "Settings", icon: "settings" },
];

type Page =
  | "dashboard" | "employees" | "add-employee" | "employee-details"
  | "managers" | "manager-details" | "attendance" | "attendance-details"
  | "leave-management" | "leave-details" | "departments" | "department-details"
  | "reports" | "settings" | "notifications" | "search";

function EmptyState({ icon, title, description }: { icon: IconName; title: string; description: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-slate-100 text-slate-400">
        <Icon name={icon} className="h-6 w-6" />
      </div>
      <p className="text-sm font-semibold text-slate-700">{title}</p>
      <p className="mt-1 text-xs text-slate-400">{description}</p>
    </div>
  );
}

function Sidebar({ open, onClose, page, onNavigate, dark }: { open: boolean; onClose: () => void; page: Page; onNavigate: (page: Page) => void; dark: boolean }) {
  return (
    <>
      {open && <button className="fixed inset-0 z-40 bg-slate-950/30 backdrop-blur-[2px] lg:hidden" aria-label="Close menu" onClick={onClose} />}
      <aside className={`fixed inset-y-0 left-0 z-50 flex w-[260px] flex-col border-r transition-all duration-300 lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"} ${dark ? "border-purple-900/40 bg-[#130f23]" : "border-slate-200 bg-white"}`}>
        <div className={`flex h-20 items-center justify-between border-b px-6 ${dark ? "border-purple-900/40" : "border-slate-100"}`}>
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-indigo-600 text-white shadow-sm shadow-indigo-200">
              <Icon name="userCheck" className="h-5 w-5" />
            </div>
            <div>
              <p className={`text-[15px] font-bold leading-tight ${dark ? "text-white" : "text-slate-900"}`}>Attendance</p>
              <p className={`text-xs font-medium ${dark ? "text-purple-400" : "text-slate-500"}`}>System</p>
            </div>
          </div>
          <button className={`rounded-lg p-2 lg:hidden ${dark ? "text-slate-400 hover:bg-purple-900/40" : "text-slate-500 hover:bg-slate-100"}`} onClick={onClose} aria-label="Close navigation">
            <Icon name="close" />
          </button>
        </div>
        <nav className="flex-1 overflow-y-auto px-4 py-6">
          <p className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[0.15em] text-slate-400">Workspace</p>
          <div className="space-y-1.5">
            {navItems.map((item) => (
              <button
                key={item.name}
                onClick={() => { onNavigate(item.name.toLowerCase().replace(" ", "-") as Page); onClose(); }}
                className={`flex w-full items-center gap-3 rounded-xl px-3.5 py-3 text-left text-sm font-medium transition-colors ${
                  page === item.name.toLowerCase().replace(" ", "-")
                    ? dark ? "bg-purple-900/50 text-purple-300" : "bg-indigo-50 text-indigo-700"
                    : dark ? "text-slate-400 hover:bg-purple-900/30 hover:text-slate-200" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                }`}
              >
                <Icon name={item.icon} className="h-[19px] w-[19px]" />
                {item.name}
                {page === item.name.toLowerCase().replace(" ", "-") && <span className={`ml-auto h-1.5 w-1.5 rounded-full ${dark ? "bg-purple-400" : "bg-indigo-600"}`} />}
              </button>
            ))}
          </div>
        </nav>
        <div className={`border-t p-4 ${dark ? "border-purple-900/40" : "border-slate-100"}`}>
          <div className="mb-2 flex items-center gap-3 rounded-xl px-3 py-2">
            <span className="grid h-9 w-9 place-items-center rounded-full bg-indigo-100 text-xs font-bold text-indigo-700">AD</span>
            <div className="min-w-0">
              <p className={`truncate text-xs font-bold ${dark ? "text-white" : "text-slate-800"}`}>Alex Davis</p>
              <p className="text-[10px] text-slate-400">Super Admin</p>
            </div>
          </div>
          <button className={`flex w-full items-center gap-3 rounded-xl px-3.5 py-3 text-sm font-medium ${dark ? "text-slate-400 hover:bg-rose-950/40 hover:text-rose-400" : "text-slate-600 hover:bg-red-50 hover:text-red-600"}`}>
            <Icon name="logout" className="h-[19px] w-[19px]" />
            Logout
          </button>
          <div className={`mt-3 rounded-xl px-3.5 py-3 ${dark ? "bg-purple-900/30" : "bg-slate-50"}`}>
            <p className={`text-xs font-semibold ${dark ? "text-purple-300" : "text-slate-700"}`}>HR Management Suite</p>
            <p className="mt-0.5 text-[11px] text-slate-400">Version 2.4.0</p>
          </div>
        </div>
      </aside>
    </>
  );
}

function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`rounded-2xl border border-slate-200/80 bg-white shadow-[0_1px_3px_rgba(15,23,42,0.03)] dark:border-purple-900/40 dark:bg-[#1a1330] dark:shadow-black/20 ${className}`}>{children}</section>;
}

const statDefs: { label: string; icon: IconName; color: string }[] = [
  { label: "Total Employees", icon: "users", color: "bg-indigo-50 text-indigo-600" },
  { label: "Present Today", icon: "userCheck", color: "bg-emerald-50 text-emerald-600" },
  { label: "Absent Today", icon: "userX", color: "bg-rose-50 text-rose-600" },
  { label: "On Leave", icon: "briefcase", color: "bg-amber-50 text-amber-600" },
];

function StatCard({ stat }: { stat: typeof statDefs[number] }) {
  return (
    <Card className="p-5 transition-transform duration-200 hover:-translate-y-0.5 hover:shadow-md">
      <div className="flex items-start justify-between">
        <div className={`grid h-11 w-11 place-items-center rounded-xl ${stat.color}`}>
          <Icon name={stat.icon} className="h-5 w-5" />
        </div>
      </div>
      <p className="mt-5 text-[13px] font-medium text-slate-500">{stat.label}</p>
      <p className="mt-1 text-2xl font-bold tracking-tight text-slate-900">—</p>
      <p className="mt-2 text-xs text-slate-400">No data yet</p>
    </Card>
  );
}

function AttendanceChart() {
  return (
    <Card className="min-w-0 p-5 sm:p-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-bold text-slate-900">Attendance Overview</h2>
          <p className="mt-1 text-xs text-slate-500">Daily attendance trends</p>
        </div>
        <div className="flex items-center gap-4 text-xs font-medium text-slate-500">
          <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-indigo-600" />This week</span>
          <span className="flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-slate-300" />Last week</span>
          <button className="ml-auto flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1.5 text-slate-600 sm:ml-1">
            Weekly <Icon name="chevronDown" className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      <div className="mt-7 flex h-52">
        <div className="flex w-9 flex-col justify-between pb-6 text-[10px] text-slate-400">
          <span>100%</span><span>75%</span><span>50%</span><span>25%</span><span>0%</span>
        </div>
        <div className="relative min-w-0 flex-1">
          <div className="absolute inset-x-0 top-1 h-px bg-slate-100" />
          <div className="absolute inset-x-0 top-[25%] h-px bg-slate-100" />
          <div className="absolute inset-x-0 top-[50%] h-px bg-slate-100" />
          <div className="absolute inset-x-0 top-[75%] h-px bg-slate-100" />
          <div className="absolute inset-x-0 bottom-6 top-0 flex items-center justify-center">
            <p className="text-xs text-slate-400">No attendance data yet</p>
          </div>
          <div className="absolute inset-x-0 bottom-0 flex justify-between text-[10px] text-slate-400">
            {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => <span key={d}>{d}</span>)}
          </div>
        </div>
      </div>
    </Card>
  );
}

function DepartmentOverview() {
  return (
    <Card className="p-5 sm:p-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-base font-bold text-slate-900">Department Overview</h2>
          <p className="mt-1 text-xs text-slate-500">Today's attendance by team</p>
        </div>
        <button className="text-xs font-semibold text-indigo-600 hover:text-indigo-700">View all</button>
      </div>
      <EmptyState icon="building" title="No departments yet" description="Add departments to see attendance breakdowns." />
    </Card>
  );
}

function AttendanceTable() {
  return (
    <Card className="overflow-hidden">
      <div className="flex items-center justify-between p-5 sm:p-6">
        <div>
          <h2 className="text-base font-bold text-slate-900">Today's Attendance</h2>
          <p className="mt-1 text-xs text-slate-500">Live employee attendance log</p>
        </div>
        <button className="flex items-center gap-1 text-xs font-semibold text-indigo-600 hover:text-indigo-700">View all <Icon name="arrowRight" className="h-3.5 w-3.5" /></button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[680px] text-left">
          <thead className="border-y border-slate-100 bg-slate-50/80 text-[10px] font-bold uppercase tracking-wider text-slate-400">
            <tr>
              <th className="px-6 py-3.5">Employee</th>
              <th className="px-4 py-3.5">Department</th>
              <th className="px-4 py-3.5">Check in</th>
              <th className="px-4 py-3.5">Check out</th>
              <th className="px-6 py-3.5">Status</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td colSpan={5}>
                <EmptyState icon="calendar" title="No attendance records" description="Attendance entries will appear here once employees check in." />
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function RecentActivity() {
  return (
    <Card className="p-5 sm:p-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-slate-900">Recent Activity</h2>
          <p className="mt-1 text-xs text-slate-500">Latest updates across your team</p>
        </div>
        <button className="text-xs font-semibold text-indigo-600">View all</button>
      </div>
      <EmptyState icon="clock" title="No recent activity" description="Actions like check-ins and leave requests will appear here." />
    </Card>
  );
}

const quickActions: { label: string; icon: IconName; color: string; page: Page }[] = [
  { label: "Add Employee", icon: "plus", color: "bg-indigo-50 text-indigo-600", page: "add-employee" },
  { label: "Manage Employees", icon: "users", color: "bg-sky-50 text-sky-600", page: "employees" },
  { label: "View Attendance", icon: "clock", color: "bg-emerald-50 text-emerald-600", page: "attendance" },
  { label: "Generate Report", icon: "report", color: "bg-amber-50 text-amber-600", page: "reports" },
];

function QuickActions({ onNavigate }: { onNavigate: (page: Page) => void }) {
  return (
    <Card className="p-5 sm:p-6">
      <h2 className="text-base font-bold text-slate-900">Quick Actions</h2>
      <p className="mt-1 text-xs text-slate-500">Frequently used shortcuts</p>
      <div className="mt-5 grid grid-cols-2 gap-3">
        {quickActions.map((action) => (
          <button onClick={() => onNavigate(action.page)} key={action.label} className="group rounded-xl border border-slate-100 p-3 text-left transition-all hover:border-indigo-100 hover:bg-indigo-50/30 hover:shadow-sm">
            <span className={`grid h-9 w-9 place-items-center rounded-lg ${action.color}`}>
              <Icon name={action.icon} className="h-4 w-4" />
            </span>
            <span className="mt-3 block text-[11px] font-semibold leading-4 text-slate-700">{action.label}</span>
          </button>
        ))}
      </div>
    </Card>
  );
}

function PageHeader({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h2 className="text-2xl font-bold tracking-tight text-slate-900">{title}</h2>
        <p className="mt-1.5 text-sm text-slate-500">{description}</p>
      </div>
      {action}
    </div>
  );
}

function PrimaryButton({ children, onClick }: { children: ReactNode; onClick?: () => void }) {
  return <button onClick={onClick} className="flex w-fit items-center justify-center gap-2 rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-semibold text-white shadow-sm shadow-indigo-200 transition hover:bg-indigo-700">{children}</button>;
}

function SecondaryButton({ children, onClick }: { children: ReactNode; onClick?: () => void }) {
  return <button onClick={onClick} className="flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-semibold text-slate-600 transition hover:bg-slate-50">{children}</button>;
}

function Toolbar({ search = "Search...", children }: { search?: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row">
      <label className="relative min-w-0 flex-1">
        <Icon name="search" className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        <input className="h-10 w-full rounded-xl border border-slate-200 bg-slate-50 pl-10 pr-3 text-xs outline-none focus:border-indigo-300 focus:bg-white" placeholder={search} />
      </label>
      {children}
    </div>
  );
}

function SelectControl({ children }: { children: ReactNode }) {
  return <button className="flex h-10 items-center justify-between gap-4 rounded-xl border border-slate-200 bg-white px-3.5 text-xs font-medium text-slate-600">{children}<Icon name="chevronDown" className="h-3.5 w-3.5 text-slate-400" /></button>;
}

function SmallStats({ items }: { items: { label: string; icon: IconName; color?: string }[] }) {
  return (
    <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        <Card className="flex items-center gap-4 p-5" key={item.label}>
          <span className={`grid h-11 w-11 place-items-center rounded-xl ${item.color || "bg-indigo-50 text-indigo-600"}`}><Icon name={item.icon} className="h-5 w-5" /></span>
          <div><p className="text-xs font-medium text-slate-500">{item.label}</p><p className="mt-1 text-xl font-bold text-slate-900">—</p></div>
        </Card>
      ))}
    </div>
  );
}

function Toggle({ on = false }: { on?: boolean }) {
  return <button className={`relative h-6 w-11 rounded-full transition ${on ? "bg-indigo-600" : "bg-slate-200"}`}><span className={`absolute top-1 h-4 w-4 rounded-full bg-white shadow transition ${on ? "left-6" : "left-1"}`} /></button>;
}

// ─── Pages ────────────────────────────────────────────────────────────────────

function EmployeesPage({ navigate }: { navigate: (page: Page) => void }) {
  return (
    <>
      <PageHeader title="Employees" description="Manage employee profiles, roles, and account access." action={<PrimaryButton onClick={() => navigate("add-employee")}><Icon name="plus" className="h-4 w-4" />Add Employee</PrimaryButton>} />
      <Card className="overflow-hidden">
        <Toolbar search="Search by name, ID, or email..."><SelectControl>All departments</SelectControl><SelectControl>All statuses</SelectControl></Toolbar>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1000px] text-left text-xs">
            <thead className="bg-slate-50 text-[10px] uppercase tracking-wider text-slate-400">
              <tr>{["Employee ID", "Name", "Email", "Department", "Role", "Joining Date", "Status", "Actions"].map(h => <th className="px-5 py-3.5" key={h}>{h}</th>)}</tr>
            </thead>
            <tbody>
              <tr><td colSpan={8}><EmptyState icon="users" title="No employees yet" description="Add your first employee to get started." /></td></tr>
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}

const formFields = ["First Name", "Last Name", "Employee ID", "Email", "Phone", "Department", "Role", "Date of Joining", "Manager", "Status"];

function AddEmployeePage({ navigate }: { navigate: (page: Page) => void }) {
  return (
    <>
      <PageHeader title="Add Employee" description="Create a new employee profile and assign their organization details." />
      <Card className="mx-auto max-w-4xl p-5 sm:p-8">
        <div className="mb-7 flex items-center gap-4 border-b border-slate-100 pb-7">
          <span className="grid h-20 w-20 place-items-center rounded-full bg-slate-100 text-slate-400"><Icon name="users" className="h-7 w-7" /></span>
          <div><p className="text-sm font-bold text-slate-800">Profile Photo</p><p className="mt-1 text-xs text-slate-400">PNG or JPG, maximum 2MB.</p><button className="mt-2 text-xs font-semibold text-indigo-600">Upload photo</button></div>
        </div>
        <form onSubmit={(e) => { e.preventDefault(); navigate("employees"); }}>
          <div className="grid gap-5 sm:grid-cols-2">
            {formFields.map((field) => (
              <label className="block" key={field}>
                <span className="mb-2 block text-xs font-semibold text-slate-700">{field}</span>
                {["Department", "Role", "Manager", "Status"].includes(field)
                  ? <select className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-500 outline-none"><option>Select {field.toLowerCase()}</option></select>
                  : <input type={field.includes("Date") ? "date" : field === "Email" ? "email" : "text"} className="h-11 w-full rounded-xl border border-slate-200 px-3 text-xs outline-none focus:border-indigo-300 focus:ring-2 focus:ring-indigo-50" placeholder={`Enter ${field.toLowerCase()}`} />}
              </label>
            ))}
          </div>
          <div className="mt-8 flex justify-end gap-3 border-t border-slate-100 pt-6">
            <SecondaryButton onClick={() => navigate("employees")}>Cancel</SecondaryButton>
            <PrimaryButton>Save Employee</PrimaryButton>
          </div>
        </form>
      </Card>
    </>
  );
}

function PersonDetailsPage({ kind, navigate }: { kind: "Employee" | "Manager"; navigate: (page: Page) => void }) {
  const manager = kind === "Manager";
  return (
    <>
      <PageHeader title={`${kind} Details`} description={`View ${kind.toLowerCase()} profile, attendance, and team information.`} action={<SecondaryButton onClick={() => navigate(manager ? "managers" : "employees")}>Back to {manager ? "Managers" : "Employees"}</SecondaryButton>} />
      <Card className="p-6">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
          <span className="grid h-20 w-20 place-items-center rounded-2xl bg-slate-100 text-slate-400"><Icon name="users" className="h-8 w-8" /></span>
          <div className="flex-1">
            <p className="text-xl font-bold text-slate-900">—</p>
            <p className="mt-1 text-sm text-slate-500">No profile loaded</p>
          </div>
        </div>
      </Card>
      <div className="mt-6">
        <SmallStats items={manager
          ? [{ label: "Team Members", icon: "users" }, { label: "Present Today", icon: "userCheck", color: "bg-emerald-50 text-emerald-600" }, { label: "Absent Today", icon: "userX", color: "bg-rose-50 text-rose-600" }, { label: "On Leave", icon: "leave", color: "bg-amber-50 text-amber-600" }]
          : [{ label: "Attendance", icon: "report" }, { label: "Present Days", icon: "userCheck", color: "bg-emerald-50 text-emerald-600" }, { label: "Absent Days", icon: "userX", color: "bg-rose-50 text-rose-600" }, { label: "Leave Days", icon: "leave", color: "bg-amber-50 text-amber-600" }]
        } />
      </div>
      <Card className="overflow-hidden">
        <div className="flex gap-6 border-b border-slate-100 px-6 pt-4 text-xs font-semibold">
          <button className="border-b-2 border-indigo-600 px-1 pb-4 text-indigo-600">{manager ? "Team Attendance" : "Overview"}</button>
          <button className="px-1 pb-4 text-slate-400">Attendance</button>
          <button className="px-1 pb-4 text-slate-400">Leave History</button>
        </div>
        <EmptyState icon="calendar" title="No records" description="Attendance history will appear here." />
      </Card>
    </>
  );
}

function ManagersPage({ navigate }: { navigate: (page: Page) => void }) {
  return (
    <>
      <PageHeader title="Managers" description="Manage department leaders and their teams." action={<PrimaryButton><Icon name="plus" className="h-4 w-4" />Add Manager</PrimaryButton>} />
      <SmallStats items={[{ label: "Total Managers", icon: "manager" }, { label: "Active Managers", icon: "userCheck", color: "bg-emerald-50 text-emerald-600" }, { label: "Departments Managed", icon: "building", color: "bg-sky-50 text-sky-600" }]} />
      <Card className="overflow-hidden">
        <Toolbar search="Search managers..."><SelectControl>All departments</SelectControl></Toolbar>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-xs">
            <thead className="bg-slate-50 text-[10px] uppercase text-slate-400">
              <tr>{["Name", "Email", "Department", "Employees Managed", "Status", "Actions"].map(h => <th className="px-6 py-3.5" key={h}>{h}</th>)}</tr>
            </thead>
            <tbody>
              <tr><td colSpan={6}><EmptyState icon="manager" title="No managers yet" description="Add managers to assign them to departments." /></td></tr>
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}

function AttendancePage({ navigate: _navigate }: { navigate: (page: Page) => void }) {
  return (
    <>
      <PageHeader title="Attendance" description="Track and manage daily employee attendance records." action={<SecondaryButton><Icon name="report" className="h-4 w-4" />Export records</SecondaryButton>} />
      <SmallStats items={[{ label: "Present", icon: "userCheck", color: "bg-emerald-50 text-emerald-600" }, { label: "Absent", icon: "userX", color: "bg-rose-50 text-rose-600" }, { label: "Late", icon: "clock", color: "bg-amber-50 text-amber-600" }, { label: "On Leave", icon: "leave", color: "bg-sky-50 text-sky-600" }]} />
      <Card className="overflow-hidden">
        <Toolbar search="Search employee..."><SelectControl>Select date</SelectControl><SelectControl>All departments</SelectControl><SelectControl>All statuses</SelectControl></Toolbar>
        <div className="flex gap-1 border-b border-slate-100 px-4 py-3">
          {["Daily", "Weekly", "Monthly"].map((v, i) => <button className={`rounded-lg px-3 py-2 text-xs font-semibold ${i === 0 ? "bg-indigo-50 text-indigo-600" : "text-slate-400"}`} key={v}>{v}</button>)}
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-xs">
            <thead className="bg-slate-50 text-[10px] uppercase text-slate-400">
              <tr>{["Employee", "Department", "Date", "Check-in", "Check-out", "Working Hours", "Status"].map(h => <th className="px-5 py-3.5" key={h}>{h}</th>)}</tr>
            </thead>
            <tbody>
              <tr><td colSpan={7}><EmptyState icon="calendar" title="No attendance records" description="Records will appear here once employees check in." /></td></tr>
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}

function AttendanceDetailsPage({ navigate }: { navigate: (page: Page) => void }) {
  return (
    <>
      <PageHeader title="Attendance Details" description="View individual attendance record." action={<SecondaryButton onClick={() => navigate("attendance")}>Back to Attendance</SecondaryButton>} />
      <SmallStats items={[{ label: "Present Days", icon: "userCheck", color: "bg-emerald-50 text-emerald-600" }, { label: "Absent Days", icon: "userX", color: "bg-rose-50 text-rose-600" }, { label: "Late Days", icon: "clock", color: "bg-amber-50 text-amber-600" }, { label: "Attendance %", icon: "report" }]} />
      <Card className="p-8">
        <EmptyState icon="calendar" title="No record selected" description="Select an employee from the attendance page to view details." />
      </Card>
    </>
  );
}

function LeavePage({ navigate }: { navigate: (page: Page) => void }) {
  return (
    <>
      <PageHeader title="Leave Management" description="Review and manage employee leave requests." />
      <SmallStats items={[{ label: "Pending Requests", icon: "clock", color: "bg-amber-50 text-amber-600" }, { label: "Approved", icon: "userCheck", color: "bg-emerald-50 text-emerald-600" }, { label: "Rejected", icon: "userX", color: "bg-rose-50 text-rose-600" }, { label: "Total Leave", icon: "leave" }]} />
      <Card className="overflow-hidden">
        <Toolbar search="Search leave requests..."><SelectControl>All statuses</SelectControl><SelectControl>All departments</SelectControl><SelectControl>Leave type</SelectControl></Toolbar>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1050px] text-left text-xs">
            <thead className="bg-slate-50 text-[10px] uppercase text-slate-400">
              <tr>{["Employee", "Department", "Leave Type", "Start Date", "End Date", "Days", "Reason", "Status", "Actions"].map(h => <th className="px-4 py-3.5" key={h}>{h}</th>)}</tr>
            </thead>
            <tbody>
              <tr><td colSpan={9}><EmptyState icon="leave" title="No leave requests" description="Leave requests submitted by employees will appear here." /></td></tr>
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}

function LeaveDetailsPage({ navigate }: { navigate: (page: Page) => void }) {
  return (
    <>
      <PageHeader title="Leave Request Details" description="Review request information and approval history." action={<SecondaryButton onClick={() => navigate("leave-management")}>Back</SecondaryButton>} />
      <Card className="p-8">
        <EmptyState icon="leave" title="No request selected" description="Select a leave request from the leave management page." />
      </Card>
    </>
  );
}

function DepartmentsPage({ navigate: _navigate }: { navigate: (page: Page) => void }) {
  return (
    <>
      <PageHeader title="Departments" description="Manage company departments and monitor team performance." action={<PrimaryButton><Icon name="plus" className="h-4 w-4" />Add Department</PrimaryButton>} />
      <Card className="p-8">
        <EmptyState icon="building" title="No departments yet" description="Create your first department to organize your workforce." />
      </Card>
    </>
  );
}

function DepartmentDetailsPage({ navigate }: { navigate: (page: Page) => void }) {
  return (
    <>
      <PageHeader title="Department Details" description="Department employees and attendance performance." action={<SecondaryButton onClick={() => navigate("departments")}>Back to Departments</SecondaryButton>} />
      <Card className="p-8">
        <EmptyState icon="building" title="No department selected" description="Select a department to view its details." />
      </Card>
    </>
  );
}

function ReportsPage() {
  const reportTypes = [
    { name: "Attendance Report", icon: "calendar" as IconName, color: "bg-indigo-50 text-indigo-600" },
    { name: "Employee Report", icon: "users" as IconName, color: "bg-sky-50 text-sky-600" },
    { name: "Leave Report", icon: "leave" as IconName, color: "bg-amber-50 text-amber-600" },
    { name: "Department Report", icon: "building" as IconName, color: "bg-emerald-50 text-emerald-600" },
  ];
  return (
    <>
      <PageHeader title="Reports" description="Generate and export workforce reports and insights." />
      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {reportTypes.map((r, i) => (
          <Card className={`cursor-pointer p-5 ${i === 0 ? "border-indigo-200 ring-2 ring-indigo-50" : ""}`} key={r.name}>
            <span className={`grid h-10 w-10 place-items-center rounded-xl ${r.color}`}><Icon name={r.icon} className="h-5 w-5" /></span>
            <p className="mt-4 text-sm font-bold">{r.name}</p>
            <p className="mt-1 text-xs text-slate-400">View detailed analytics</p>
          </Card>
        ))}
      </div>
      <Card className="mb-6 p-5">
        <div className="grid gap-4 md:grid-cols-4">
          <label><span className="mb-2 block text-xs font-semibold">Date Range</span><input type="date" className="h-10 w-full rounded-xl border border-slate-200 px-3 text-xs" /></label>
          {["Department", "Employee", "Report Type"].map(x => <label key={x}><span className="mb-2 block text-xs font-semibold">{x}</span><SelectControl>All {x.toLowerCase()}s</SelectControl></label>)}
        </div>
        <div className="mt-5 flex gap-3">
          <PrimaryButton>Generate Report</PrimaryButton>
          <SecondaryButton>Export PDF</SecondaryButton>
          <SecondaryButton>Export CSV</SecondaryButton>
        </div>
      </Card>
      <Card className="p-8">
        <EmptyState icon="report" title="No report generated" description="Configure filters above and click Generate Report." />
      </Card>
    </>
  );
}

function SettingsPage() {
  return (
    <>
      <PageHeader title="Settings" description="Manage your account and attendance system preferences." />
      <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
        <Card className="h-fit p-3">
          {["Profile Settings", "Security", "Attendance Settings", "Notifications"].map((x, i) => (
            <button className={`w-full rounded-xl px-3 py-3 text-left text-xs font-semibold ${i === 0 ? "bg-indigo-50 text-indigo-600" : "text-slate-500 hover:bg-slate-50"}`} key={x}>{x}</button>
          ))}
        </Card>
        <div className="space-y-6">
          <Card className="p-6">
            <h3 className="font-bold">Profile Settings</h3>
            <p className="mt-1 text-xs text-slate-400">Update your personal information.</p>
            <div className="mt-6 grid gap-5 sm:grid-cols-2">
              {["Full Name", "Email Address", "Phone Number"].map(x => (
                <label key={x}><span className="mb-2 block text-xs font-semibold">{x}</span><input className="h-11 w-full rounded-xl border border-slate-200 px-3 text-xs outline-none focus:border-indigo-300" placeholder={`Enter ${x.toLowerCase()}`} /></label>
              ))}
            </div>
          </Card>
          <Card className="p-6">
            <h3 className="font-bold">Attendance Settings</h3>
            <div className="mt-5 grid gap-5 sm:grid-cols-2">
              {["Working hours", "Late threshold", "Check-in rule", "Check-out rule"].map(x => (
                <label key={x}><span className="mb-2 block text-xs font-semibold">{x}</span><input className="h-11 w-full rounded-xl border border-slate-200 px-3 text-xs" placeholder={`Set ${x.toLowerCase()}`} /></label>
              ))}
            </div>
          </Card>
          <Card className="p-6">
            <h3 className="font-bold">Notification Settings</h3>
            <div className="mt-5 divide-y divide-slate-100">
              {["Email notifications", "Leave request notifications", "Daily attendance notifications", "System updates"].map(x => (
                <div className="flex items-center justify-between py-4" key={x}>
                  <div><p className="text-xs font-semibold">{x}</p><p className="mt-1 text-[11px] text-slate-400">Receive {x.toLowerCase()}.</p></div>
                  <Toggle />
                </div>
              ))}
            </div>
          </Card>
          <div className="flex justify-end gap-3">
            <SecondaryButton>Cancel</SecondaryButton>
            <PrimaryButton>Save Changes</PrimaryButton>
          </div>
        </div>
      </div>
    </>
  );
}

function NotificationsPage() {
  return (
    <>
      <PageHeader title="Notifications" description="Stay updated with attendance, leave, and system activity." action={<div className="flex gap-2"><SecondaryButton>Clear all</SecondaryButton><PrimaryButton>Mark all as read</PrimaryButton></div>} />
      <Card className="overflow-hidden">
        <div className="flex gap-5 border-b border-slate-100 px-6 pt-4 text-xs font-semibold">
          {["All", "Attendance", "Leave", "Employee", "System"].map((x, i) => (
            <button className={`pb-4 ${i === 0 ? "border-b-2 border-indigo-600 text-indigo-600" : "text-slate-400"}`} key={x}>{x}</button>
          ))}
        </div>
        <EmptyState icon="bell" title="No notifications" description="You're all caught up. New alerts will appear here." />
      </Card>
    </>
  );
}

function SearchPage({ navigate: _navigate }: { navigate: (page: Page) => void }) {
  return (
    <>
      <PageHeader title="Global Search" description="Search across employees, managers, departments, and records." />
      <Card className="mx-auto max-w-4xl overflow-hidden">
        <div className="relative p-5">
          <Icon name="search" className="absolute left-8 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
          <input autoFocus className="h-12 w-full rounded-xl border border-slate-200 bg-slate-50 pl-11 pr-4 text-sm outline-none focus:border-indigo-300 focus:ring-2 focus:ring-indigo-50" placeholder="Search employees, departments, records..." />
        </div>
        <div className="border-t border-slate-100 p-5">
          <EmptyState icon="search" title="Start typing to search" description="Results for employees, managers, departments and records will appear here." />
        </div>
      </Card>
    </>
  );
}

// ─── Upcoming Holidays ────────────────────────────────────────────────────────

const HOLIDAY_MAP: Record<string, string> = {};
const MONTH_NAMES = ["January","February","March","April","May","June","July","August","September","October","November","December"];
function pad(n: number) { return String(n).padStart(2, "0"); }

function UpcomingHolidays() {
  const today = new Date();
  const [calOpen, setCalOpen] = useState(false);
  const [calYear, setCalYear] = useState(today.getFullYear());
  const [calMonth, setCalMonth] = useState(today.getMonth());
  const calRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleOutside(e: MouseEvent) {
      if (calRef.current && !calRef.current.contains(e.target as Node)) setCalOpen(false);
    }
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, []);

  function prevMonth() {
    if (calMonth === 0) { setCalMonth(11); setCalYear(y => y - 1); }
    else setCalMonth(m => m - 1);
  }
  function nextMonth() {
    if (calMonth === 11) { setCalMonth(0); setCalYear(y => y + 1); }
    else setCalMonth(m => m + 1);
  }

  const firstDay = new Date(calYear, calMonth, 1).getDay();
  const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();
  const cells: (number | null)[] = [...Array(firstDay).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => i + 1)];
  while (cells.length % 7 !== 0) cells.push(null);

  const years = Array.from({ length: 10 }, (_, i) => today.getFullYear() - 1 + i);

  const holidaysThisMonth = Object.entries(HOLIDAY_MAP).filter(([k]) => {
    const [y, m] = k.split("-").map(Number);
    return y === calYear && m - 1 === calMonth;
  });

  return (
    <Card className="p-5 sm:p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-sm font-bold text-slate-800">Upcoming Holidays</p>
          <p className="text-[11px] text-slate-400">Public holidays</p>
        </div>
        <div ref={calRef} className="relative">
          <button
            onClick={() => setCalOpen(o => !o)}
            className={`grid h-8 w-8 place-items-center rounded-lg transition-colors ${calOpen ? "bg-indigo-100" : "bg-indigo-50 hover:bg-indigo-100"}`}
            aria-label="Toggle calendar"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-indigo-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
          </button>
          {calOpen && (
            <div className="absolute right-0 top-full z-50 mt-2 w-72 rounded-2xl border border-slate-200 bg-white p-4 shadow-xl shadow-slate-200/70">
              <div className="mb-3 flex items-center gap-1.5">
                <button onClick={prevMonth} className="grid h-7 w-7 place-items-center rounded-lg text-slate-500 hover:bg-slate-100">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
                </button>
                <select value={calMonth} onChange={e => setCalMonth(Number(e.target.value))} className="flex-1 rounded-lg border border-slate-200 bg-slate-50 px-2 py-1 text-center text-xs font-semibold text-slate-700 outline-none focus:border-indigo-300">
                  {MONTH_NAMES.map((m, i) => <option key={m} value={i}>{m}</option>)}
                </select>
                <select value={calYear} onChange={e => setCalYear(Number(e.target.value))} className="w-20 rounded-lg border border-slate-200 bg-slate-50 px-2 py-1 text-center text-xs font-semibold text-slate-700 outline-none focus:border-indigo-300">
                  {years.map(y => <option key={y} value={y}>{y}</option>)}
                </select>
                <button onClick={nextMonth} className="grid h-7 w-7 place-items-center rounded-lg text-slate-500 hover:bg-slate-100">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
                </button>
              </div>
              <div className="mb-1 grid grid-cols-7 text-center">
                {["Su","Mo","Tu","We","Th","Fr","Sa"].map(d => (
                  <span key={d} className="text-[9px] font-bold uppercase tracking-wide text-slate-400">{d}</span>
                ))}
              </div>
              <div className="grid grid-cols-7 gap-y-0.5">
                {cells.map((day, idx) => {
                  if (!day) return <div key={idx} />;
                  const key = `${calYear}-${pad(calMonth + 1)}-${pad(day)}`;
                  const isHoliday = Boolean(HOLIDAY_MAP[key]);
                  const isToday = today.getFullYear() === calYear && today.getMonth() === calMonth && today.getDate() === day;
                  return (
                    <div key={idx} className="relative flex flex-col items-center py-0.5" title={isHoliday ? HOLIDAY_MAP[key] : undefined}>
                      <span className={`flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-medium ${isHoliday ? "bg-indigo-500 font-bold text-white" : isToday ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-100"}`}>
                        {day}
                      </span>
                      {isHoliday && <span className="mt-0.5 h-1 w-1 rounded-full bg-indigo-400" />}
                    </div>
                  );
                })}
              </div>
              <div className="mt-3 flex flex-col gap-1 border-t border-slate-100 pt-3">
                {holidaysThisMonth.length > 0
                  ? holidaysThisMonth.map(([k, name]) => (
                    <div key={k} className="flex items-center gap-2">
                      <span className="rounded bg-indigo-50 px-1.5 py-0.5 text-[9px] font-bold text-indigo-700">{k.slice(5)}</span>
                      <span className="text-[10px] text-slate-600">{name}</span>
                    </div>
                  ))
                  : <p className="text-[10px] text-slate-400">No holidays this month</p>
                }
              </div>
            </div>
          )}
        </div>
      </div>
      <EmptyState icon="calendar" title="No holidays configured" description="Holidays will appear here once added." />
    </Card>
  );
}

// ─── Dashboard ────────────────────────────────────────────────────────────────

function DashboardPage({ navigate }: { navigate: (page: Page) => void }) {
  return (
    <>
      <div className="mb-6">
        <p className="text-2xl font-bold tracking-tight text-slate-900 sm:text-[28px]">Welcome back, Admin</p>
        <p className="mt-1.5 text-sm text-slate-500">Here's what's happening with your workforce today.</p>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {statDefs.map((stat) => <StatCard stat={stat} key={stat.label} />)}
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.65fr)_minmax(300px,0.75fr)]">
        <AttendanceChart />
        <UpcomingHolidays />
      </div>
      <div className="mt-6 grid items-start gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(300px,0.75fr)]">
        <AttendanceTable />
        <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-1">
          <QuickActions onNavigate={navigate} />
          <RecentActivity />
          <DepartmentOverview />
        </div>
      </div>
    </>
  );
}

// ─── App ──────────────────────────────────────────────────────────────────────

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [page, setPage] = useState<Page>("dashboard");
  const [profileOpen, setProfileOpen] = useState(false);
  const [dark, setDark] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) setProfileOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const navigate = (next: Page) => { setPage(next); window.scrollTo({ top: 0, behavior: "smooth" }); };

  const titles: Record<Page, string> = {
    dashboard: "Super Admin Dashboard", employees: "Employees", "add-employee": "Add Employee", "employee-details": "Employee Details",
    managers: "Managers", "manager-details": "Manager Details", attendance: "Attendance", "attendance-details": "Attendance Details",
    "leave-management": "Leave Management", "leave-details": "Leave Request Details", departments: "Departments", "department-details": "Department Details",
    reports: "Reports", settings: "Settings", notifications: "Notifications", search: "Global Search",
  };

  const content: Record<Page, ReactNode> = {
    dashboard: <DashboardPage navigate={navigate} />,
    employees: <EmployeesPage navigate={navigate} />,
    "add-employee": <AddEmployeePage navigate={navigate} />,
    "employee-details": <PersonDetailsPage kind="Employee" navigate={navigate} />,
    managers: <ManagersPage navigate={navigate} />,
    "manager-details": <PersonDetailsPage kind="Manager" navigate={navigate} />,
    attendance: <AttendancePage navigate={navigate} />,
    "attendance-details": <AttendanceDetailsPage navigate={navigate} />,
    "leave-management": <LeavePage navigate={navigate} />,
    "leave-details": <LeaveDetailsPage navigate={navigate} />,
    departments: <DepartmentsPage navigate={navigate} />,
    "department-details": <DepartmentDetailsPage navigate={navigate} />,
    reports: <ReportsPage />,
    settings: <SettingsPage />,
    notifications: <NotificationsPage />,
    search: <SearchPage navigate={navigate} />,
  };

  return (
    <div className={`min-h-screen transition-colors duration-300 ${dark ? "dark bg-[#0d0d1a] text-slate-100" : "bg-slate-50 text-slate-900"}`}>
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} page={page} onNavigate={navigate} dark={dark} />
      <div className="lg:pl-[260px]">
        <header className={`sticky top-0 z-30 flex h-20 items-center border-b px-4 backdrop-blur sm:px-6 lg:px-8 ${dark ? "border-purple-900/40 bg-[#130f23]/95" : "border-slate-200/80 bg-white/95"}`}>
          <button className={`mr-3 rounded-lg p-2 lg:hidden ${dark ? "text-slate-300 hover:bg-purple-900/40" : "text-slate-600 hover:bg-slate-100"}`} onClick={() => setSidebarOpen(true)} aria-label="Open navigation"><Icon name="menu" /></button>
          <div>
            <h1 className={`text-lg font-bold tracking-tight ${dark ? "text-white" : "text-slate-900"}`}>{titles[page]}</h1>
            <p className="hidden text-xs text-slate-400 sm:block">{new Date().toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}</p>
          </div>
          <div className="ml-auto flex items-center gap-2 sm:gap-3">
            <label className="relative hidden md:block">
              <span className="sr-only">Search</span>
              <Icon name="search" className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input onFocus={() => navigate("search")} className={`h-10 w-56 rounded-xl border pl-10 pr-4 text-xs outline-none transition xl:w-64 ${dark ? "border-purple-800/50 bg-purple-900/20 text-slate-200 placeholder:text-slate-500 focus:border-purple-500 focus:bg-purple-900/30" : "border-slate-200 bg-slate-50 focus:border-indigo-300 focus:bg-white focus:ring-2 focus:ring-indigo-100"}`} placeholder="Search anything..." />
            </label>
            <button onClick={() => navigate("search")} className={`grid h-10 w-10 place-items-center rounded-xl border md:hidden ${dark ? "border-purple-800/50 text-slate-400 hover:bg-purple-900/30" : "border-slate-200 text-slate-500 hover:bg-slate-50"}`} aria-label="Search"><Icon name="search" className="h-[18px] w-[18px]" /></button>
            <button onClick={() => navigate("notifications")} className={`relative grid h-10 w-10 place-items-center rounded-xl border ${dark ? "border-purple-800/50 text-slate-400 hover:bg-purple-900/30" : "border-slate-200 text-slate-500 hover:bg-slate-50"}`} aria-label="Notifications">
              <Icon name="bell" className="h-[18px] w-[18px]" />
            </button>
            <button
              onClick={() => setDark(d => !d)}
              className={`grid h-10 w-10 place-items-center rounded-xl border transition-colors ${dark ? "border-purple-700 bg-purple-900/40 text-purple-300 hover:bg-purple-800/50" : "border-slate-200 text-slate-500 hover:bg-slate-50"}`}
              aria-label="Toggle theme"
            >
              {dark
                ? <svg xmlns="http://www.w3.org/2000/svg" className="h-[18px] w-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
                : <svg xmlns="http://www.w3.org/2000/svg" className="h-[18px] w-[18px]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
              }
            </button>
            <div className={`mx-1 hidden h-7 w-px sm:block ${dark ? "bg-purple-900/50" : "bg-slate-200"}`} />
            <div ref={profileRef} className="relative">
              <button onClick={() => setProfileOpen(o => !o)} className={`flex items-center gap-2.5 rounded-xl p-1.5 ${dark ? "hover:bg-purple-900/40" : "hover:bg-slate-50"}`} aria-haspopup="true" aria-expanded={profileOpen}>
                <span className="grid h-9 w-9 place-items-center rounded-full bg-indigo-100 text-xs font-bold text-indigo-700">AD</span>
                <span className="hidden text-left xl:block">
                  <span className={`block text-xs font-bold ${dark ? "text-white" : "text-slate-800"}`}>Alex Davis</span>
                  <span className="block text-[10px] text-slate-400">Super Admin</span>
                </span>
                <Icon name="chevronDown" className={`hidden h-4 w-4 xl:block transition-transform duration-200 ${profileOpen ? "rotate-180" : ""} ${dark ? "text-slate-500" : "text-slate-400"}`} />
              </button>
              {profileOpen && (
                <div className={`absolute right-0 top-full z-50 mt-2 w-48 rounded-xl border py-1.5 shadow-lg ${dark ? "border-purple-800/50 bg-[#1a1330] shadow-black/40" : "border-slate-200 bg-white shadow-slate-200/60"}`}>
                  <div className={`border-b px-4 py-2.5 xl:hidden ${dark ? "border-purple-900/50" : "border-slate-100"}`}>
                    <p className={`text-xs font-bold ${dark ? "text-white" : "text-slate-800"}`}>Alex Davis</p>
                    <p className="text-[10px] text-slate-400">Super Admin</p>
                  </div>
                  <button onClick={() => { navigate("settings"); setProfileOpen(false); }} className={`flex w-full items-center gap-3 px-4 py-2.5 text-left text-xs font-medium ${dark ? "text-slate-300 hover:bg-purple-900/40" : "text-slate-700 hover:bg-slate-50"}`}>
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
                    Settings
                  </button>
                  <div className={`my-1 border-t ${dark ? "border-purple-900/50" : "border-slate-100"}`} />
                  <button onClick={() => setProfileOpen(false)} className={`flex w-full items-center gap-3 px-4 py-2.5 text-left text-xs font-medium text-rose-500 ${dark ? "hover:bg-rose-950/40" : "hover:bg-rose-50"}`}>
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
                    Log Out
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-[1600px] p-4 sm:p-6 lg:p-8">{content[page]}</main>
      </div>
    </div>
  );
}

export default App;
