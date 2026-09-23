import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useAuth } from "../lib/auth.jsx";
import { AuthPage } from "../components/auth/AuthPage.jsx";

export const Route = createFileRoute("/admin-login")({
  head: () => ({
    meta: [
      { title: "Admin Sign in — AttendPro Attendance" },
      {
        name: "description",
        content: "Employee sign in for AttendPro attendance and leave management.",
      },
      { property: "og:title", content: "Admin Sign in — AttendPro Attendance" },
      {
        property: "og:description",
        content: "Employee sign in for AttendPro attendance and leave management.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: AdminLoginPage,
});

function AdminLoginPage() {
  const { login, isAuthenticated, ready } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (ready && isAuthenticated) {
      navigate({ to: "/dashboard", replace: true });
    }
  }, [ready, isAuthenticated, navigate]);

  async function handleSubmit(event) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await login(email.trim(), password, "admin");
      navigate({ to: "/dashboard", replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid email or password.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthPage
      title="Admin Sign in"
      subtitle="Use your admin credentials to access the management dashboard."
      email={email}
      password={password}
      showPassword={showPassword}
      onEmailChange={(e) => setEmail(e.target.value)}
      onPasswordChange={(e) => setPassword(e.target.value)}
      onTogglePassword={() => setShowPassword((v) => !v)}
      onSubmit={handleSubmit}
      error={error}
      submitting={submitting}
    />
  );
}
