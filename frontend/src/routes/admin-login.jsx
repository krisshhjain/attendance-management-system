import { createFileRoute } from "@tanstack/react-router";
import { AdminLoginPage } from "../components/AdminLoginPage.jsx";

export const Route = createFileRoute("/admin-login")({
  head: () => ({
    meta: [
      { title: "Admin Sign in ? AttendPro Attendance" },
      {
        name: "description",
        content: "Employee sign in for AttendPro attendance and leave management.",
      },
      { property: "og:title", content: "Admin Sign in ? AttendPro Attendance" },
      {
        property: "og:description",
        content: "Employee sign in for AttendPro attendance and leave management.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: () => (
    <AdminLoginPage
      loginType="admin"
      title="Admin Sign in"
      description="Use your admin credentials to access the management dashboard."
      supportMessage="Trouble signing in? Contact your HR administrator."
    />
  ),
});
