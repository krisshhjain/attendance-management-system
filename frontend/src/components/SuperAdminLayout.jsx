import { useState, useRef, useEffect } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Sidebar } from "./Sidebar.jsx";
import { useAuth } from "../lib/auth.jsx";
import { SystemAdminChatWidget } from "./SystemAdminChatWidget.jsx";

const DRAWER_WIDTH = 260;

export function SuperAdminLayout({ children, title }) {
  const { user, loginType, logout } = useAuth();
  const navigate = useNavigate();

  const email = user?.email ?? "";
  const displayName = email.split("@")[0] || "Super Admin";
  const initials = displayName.slice(0, 2).toUpperCase();

  const today = new Date().toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  // Mobile sidebar
  const [mobileOpen, setMobileOpen] = useState(false);

  // Profile dropdown
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef(null);

  // Responsive: detect mobile
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 960);
  useEffect(() => {
    const handler = () => setIsMobile(window.innerWidth < 960);
    window.addEventListener("resize", handler);
    return () => window.removeEventListener("resize", handler);
  }, []);

  // Close profile dropdown on outside click
  useEffect(() => {
    function handler(e) {
      if (profileRef.current && !profileRef.current.contains(e.target)) {
        setProfileOpen(false);
      }
    }
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleLogout = () => {
    logout();
    navigate({ to: "/login" });
  };

  return (
    <div style={{ display: "flex", minHeight: "100vh", backgroundColor: "#f8fafc" }}>
      {/* Sidebar */}
      <Sidebar
        mobileOpen={mobileOpen}
        handleDrawerToggle={() => setMobileOpen((p) => !p)}
        isMobile={isMobile}
      />

      {/* Main area */}
      <div
        style={{
          flex: 1,
          minWidth: 0,
          display: "flex",
          flexDirection: "column",
          marginLeft: isMobile ? 0 : 0, // sidebar is position:sticky so no margin needed
        }}
      >
        {/* ── Sticky Header ─────────────────────────────────────────────── */}
        <header
          style={{
            position: "sticky",
            top: 0,
            zIndex: 100,
            height: 72,
            backgroundColor: "rgba(255,255,255,0.9)",
            backdropFilter: "blur(12px)",
            borderBottom: "1px solid #e2e8f0",
            display: "flex",
            alignItems: "center",
            padding: "0 24px",
            gap: 12,
          }}
        >
          {/* Hamburger (mobile) */}
          {isMobile && (
            <button
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation"
              style={{
                border: "none",
                background: "none",
                cursor: "pointer",
                color: "#64748b",
                borderRadius: 10,
                padding: 8,
                display: "flex",
                alignItems: "center",
                marginRight: 4,
              }}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="4" y1="6" x2="20" y2="6"/>
                <line x1="4" y1="12" x2="20" y2="12"/>
                <line x1="4" y1="18" x2="20" y2="18"/>
              </svg>
            </button>
          )}

          {/* Page title + date */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <h1
              style={{
                margin: 0,
                fontSize: 18,
                fontWeight: 700,
                color: "#0f172a",
                letterSpacing: "-0.02em",
                lineHeight: 1.2,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {title || "Dashboard"}
            </h1>
            <p
              style={{
                margin: 0,
                fontSize: 12,
                color: "#94a3b8",
                marginTop: 1,
                display: isMobile ? "none" : "block",
              }}
            >
              {today}
            </p>
          </div>

          {/* Right controls */}
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {/* Profile dropdown */}
            <div ref={profileRef} style={{ position: "relative" }}>
              <button
                onClick={() => setProfileOpen((p) => !p)}
                aria-haspopup="true"
                aria-expanded={profileOpen}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "6px 10px 6px 6px",
                  borderRadius: 10,
                  border: "1px solid #e2e8f0",
                  background: "white",
                  cursor: "pointer",
                  transition: "all 0.15s",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.borderColor = "#c7d2fe")}
                onMouseLeave={(e) => (e.currentTarget.style.borderColor = "#e2e8f0")}
              >
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: "50%",
                    background: "#eef2ff",
                    color: "#4f46e5",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 11,
                    fontWeight: 700,
                    flexShrink: 0,
                  }}
                >
                  {initials}
                </div>
                {!isMobile && (
                  <div style={{ textAlign: "left" }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: "#0f172a", lineHeight: 1.2 }}>
                      {displayName}
                    </div>
                    <div style={{ fontSize: 10, color: "#94a3b8" }}>
                      {loginType === "systemadmin" ? "System Admin" : "Super Admin"}
                    </div>
                  </div>
                )}
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#94a3b8"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{
                    transform: profileOpen ? "rotate(180deg)" : "rotate(0deg)",
                    transition: "transform 0.2s",
                    flexShrink: 0,
                  }}
                >
                  <path d="m6 9 6 6 6-6"/>
                </svg>
              </button>

              {/* Dropdown */}
              {profileOpen && (
                <div
                  style={{
                    position: "absolute",
                    right: 0,
                    top: "calc(100% + 8px)",
                    width: 200,
                    backgroundColor: "#fff",
                    border: "1px solid #e2e8f0",
                    borderRadius: 12,
                    boxShadow: "0 10px 25px rgba(15,23,42,0.08), 0 4px 10px rgba(15,23,42,0.05)",
                    padding: "6px",
                    zIndex: 1000,
                  }}
                >
                  <div
                    style={{
                      padding: "8px 12px 10px",
                      borderBottom: "1px solid #f1f5f9",
                      marginBottom: 4,
                    }}
                  >
                    <div style={{ fontSize: 12, fontWeight: 700, color: "#0f172a" }}>{displayName}</div>
                    <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2 }}>{email}</div>
                  </div>
                  <button
                    onClick={() => {
                      setProfileOpen(false);
                      navigate({ to: "/settings" });
                    }}
                    style={{
                      width: "100%",
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      padding: "9px 12px",
                      fontSize: 13,
                      fontWeight: 500,
                      color: "#475569",
                      background: "none",
                      border: "none",
                      borderRadius: 8,
                      cursor: "pointer",
                      textAlign: "left",
                      transition: "all 0.1s",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "#f8fafc")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="12" r="3"/>
                      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6h.08A1.65 1.65 0 0 0 10 3.09V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9v.08A1.65 1.65 0 0 0 20.91 10H21a2 2 0 1 1 0 4h-.09A1.65 1.65 0 0 0 19.4 15z"/>
                    </svg>
                    Settings
                  </button>
                  <div style={{ height: 1, background: "#f1f5f9", margin: "4px 0" }} />
                  <button
                    onClick={handleLogout}
                    style={{
                      width: "100%",
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      padding: "9px 12px",
                      fontSize: 13,
                      fontWeight: 500,
                      color: "#e11d48",
                      background: "none",
                      border: "none",
                      borderRadius: 8,
                      cursor: "pointer",
                      textAlign: "left",
                      transition: "all 0.1s",
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = "#fff1f2")}
                    onMouseLeave={(e) => (e.currentTarget.style.background = "none")}
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M10 17l5-5-5-5M15 12H3M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>
                    </svg>
                    Log Out
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* ── Page Content ──────────────────────────────────────────────── */}
        <main
          style={{
            flex: 1,
            padding: isMobile ? "16px" : "28px 32px",
            maxWidth: 1600,
            width: "100%",
          }}
        >
          {children}
        </main>
      </div>

      {/* System Admin Chat Widget (preserved) */}
      {loginType === "systemadmin" && <SystemAdminChatWidget />}
    </div>
  );
}
