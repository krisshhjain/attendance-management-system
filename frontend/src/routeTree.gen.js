import { Route as rootRouteImport } from './routes/__root.jsx'
import { Route as IndexRouteImport } from './routes/index.jsx'
import { Route as AttendanceRouteImport } from './routes/attendance.jsx'
import { Route as DashboardRouteImport } from './routes/dashboard.jsx'
import { Route as LoginRouteImport } from './routes/login.jsx'
import { Route as AdminLoginRouteImport } from './routes/admin-login.jsx'
import { Route as SystemAdminLoginRouteImport } from './routes/systemadmin-login.jsx'
import { Route as HRCopilotRouteImport } from './routes/hr-copilot.jsx'
import { Route as SettingsRouteImport } from './routes/settings.jsx'
import { Route as LeaveRouteImport } from './routes/leave.jsx'
import { Route as AdministrationRouteImport } from './routes/administration.jsx'
import { Route as EmployeesRouteImport } from './routes/employees.jsx'

const IndexRoute = IndexRouteImport.update({
  id: '/',
  path: '/',
  getParentRoute: () => rootRouteImport,
})

const AttendanceRoute = AttendanceRouteImport.update({
  id: '/attendance',
  path: '/attendance',
  getParentRoute: () => rootRouteImport,
})

const DashboardRoute = DashboardRouteImport.update({
  id: '/dashboard',
  path: '/dashboard',
  getParentRoute: () => rootRouteImport,
})

const LoginRoute = LoginRouteImport.update({
  id: '/login',
  path: '/login',
  getParentRoute: () => rootRouteImport,
})

const AdminLoginRoute = AdminLoginRouteImport.update({
  id: '/admin-login',
  path: '/admin-login',
  getParentRoute: () => rootRouteImport,
})

const SystemAdminLoginRoute = SystemAdminLoginRouteImport.update({
  id: '/systemadmin-login',
  path: '/systemadmin-login',
  getParentRoute: () => rootRouteImport,
})

const HRCopilotRoute = HRCopilotRouteImport.update({
  id: '/hr-copilot',
  path: '/hr-copilot',
  getParentRoute: () => rootRouteImport,
})

const SettingsRoute = SettingsRouteImport.update({
  id: '/settings',
  path: '/settings',
  getParentRoute: () => rootRouteImport,
})

const LeaveRoute = LeaveRouteImport.update({
  id: '/leave',
  path: '/leave',
  getParentRoute: () => rootRouteImport,
})

const AdministrationRoute = AdministrationRouteImport.update({
  id: '/administration',
  path: '/administration',
  getParentRoute: () => rootRouteImport,
})

const EmployeesRoute = EmployeesRouteImport.update({
  id: '/employees',
  path: '/employees',
  getParentRoute: () => rootRouteImport,
})

const rootRouteChildren = {
  IndexRoute: IndexRoute,
  AttendanceRoute: AttendanceRoute,
  DashboardRoute: DashboardRoute,
  LoginRoute: LoginRoute,
  AdminLoginRoute: AdminLoginRoute,
  SystemAdminLoginRoute: SystemAdminLoginRoute,
  HRCopilotRoute: HRCopilotRoute,
  SettingsRoute: SettingsRoute,
  LeaveRoute: LeaveRoute,
  AdministrationRoute: AdministrationRoute,
  EmployeesRoute: EmployeesRoute,
}

export const routeTree = rootRouteImport._addFileChildren(rootRouteChildren)
