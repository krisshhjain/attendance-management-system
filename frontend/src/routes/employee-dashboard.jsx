/**
 * employee-dashboard.jsx
 *
 * TanStack Router route for /employee-dashboard.
 *
 * Renders the Figma Employee Dashboard UI with its own full-page layout
 * (Figma Sidebar + Header). Does NOT replace or modify the existing
 * /dashboard route used by Super Admin.
 *
 * Imports employee-dashboard.css (Tailwind utilities + dark mode CSS vars)
 * scoped to this route only — does not affect the MUI-based pages.
 */

import { createFileRoute, redirect } from "@tanstack/react-router";
import { tokenStore } from "../lib/api.js";
import EmployeeDashboardApp from "../employee-dashboard/EmployeeDashboardApp.tsx";
import "../employee-dashboard/employee-dashboard.css";

export const Route = createFileRoute("/employee-dashboard")({
  beforeLoad() {
    // Guard: redirect to login if no JWT access token is present.
    // We don't use the existing RequireAuth component because the Figma
    // dashboard has its own Sidebar + Header layout.
    if (!tokenStore.access) {
      throw redirect({ to: "/login" });
    }
  },
  component: EmployeeDashboardRouteComponent,
});

function EmployeeDashboardRouteComponent() {
  return <EmployeeDashboardApp />;
}

