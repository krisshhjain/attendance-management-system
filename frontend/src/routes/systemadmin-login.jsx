import { createFileRoute } from "@tanstack/react-router";
import { AdminLoginPage } from "../components/AdminLoginPage.jsx";

export const Route = createFileRoute("/systemadmin-login")({
  head: () => ({
    meta: [
      { title: "System Manager Sign in ? AttendPro Attendance" },
      {
        name: "description",
        content: "Employee sign in for AttendPro attendance and leave management.",
      },
      { property: "og:title", content: "System Manager Sign in ? AttendPro Attendance" },
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
      loginType="systemadmin"
      title="System Manager Sign in"
      description="Use your System Manager credentials to access the system dashboard."
      supportMessage="Trouble signing in? Contact your system manager."
    />
  ),
});
