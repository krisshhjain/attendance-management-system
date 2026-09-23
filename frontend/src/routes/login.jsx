import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useAuth } from "../lib/auth.jsx";
import { AuthPage } from "../components/auth/AuthPage.jsx";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign in — AttendPro Attendance" },
      {
        name: "description",
        content: "Employee sign in for AttendPro attendance and leave management.",
      },
      { property: "og:title", content: "Sign in — AttendPro Attendance" },
      {
        property: "og:description",
        content: "Employee sign in for AttendPro attendance and leave management.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const { login, isAuthenticated, ready, logout } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // Always force employee mode when the regular login page is visited.
  // This handles the case where an admin previously logged in via /admin-login
  // and their localStorage still says "admin".
  useEffect(() => {
    localStorage.setItem("loginType", "employee");
  }, []);

  useEffect(() => {
    if (ready && isAuthenticated) {
      // If already logged in as admin, log them out and let them re-login
      // as an employee through this route.
      const storedType = localStorage.getItem("loginType");
      if (storedType === "admin") {
        logout();
        return;
      }
      navigate({ to: "/dashboard", replace: true });
    }
  }, [ready, isAuthenticated, navigate, logout]);

  async function handleSubmit(event) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      // Explicitly pass "employee" so loginType is always forced to employee
      // regardless of whether the user is a superuser.
      await login(email.trim(), password, "employee");
      navigate({ to: "/dashboard", replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid email or password.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthPage
      title="Sign in"
      subtitle="Use your company email to access your attendance."
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
