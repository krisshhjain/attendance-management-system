import { useState } from "react";
import { Link, useLocation, useNavigate } from "@tanstack/react-router";
import { useAuth } from "../lib/auth.jsx";

const DRAWER_WIDTH = 260;

// ── Icons (inline SVG, matching Figma prototype) ──────────────────────────────
function Icon({ d, className = "" }) {
  return (
    <svg
      className={className}
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {d}
    </svg>
  );
}

const ICONS = {
  dashboard: <><rect x="3" y="3" width="7" height="7" rx="2"/><rect x="14" y="3" width="7" height="7" rx="2"/><rect x="3" y="14" width="7" height="7" rx="2"/><rect x="14" y="14" width="7" height="7" rx="2"/></>,
  attendance: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  employees: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></>,
  leave: <><path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 18 2 18 2c1 5.5-.7 12.2-7 14.5"/><path d="M2 21c2-5 5.5-8.5 10-11"/></>,
  administration: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h5"/></>,
  hrcopilot: <><circle cx="12" cy="8" r="4"/><path d="M5.5 21a6.5 6.5 0 0 1 13 0M9 14.75l3 3 3-3"/></>,
  settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6h.08A1.65 1.65 0 0 0 10 3.09V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9v.08A1.65 1.65 0 0 0 20.91 10H21a2 2 0 1 1 0 4h-.09A1.65 1.65 0 0 0 19.4 15z"/></>,
  logout: <><path d="M10 17l5-5-5-5M15 12H3M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/></>,
  close: <path d="M18 6 6 18M6 6l12 12"/>,
  usercheck: <><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><path d="M8.5 11a4 4 0 1 0 0-8"/><path d="M17 11l2 2 4-4"/></>,
};

// ── Nav items — all existing routes preserved ─────────────────────────────────
function getNavItems(loginType) {
  const items = [
    { text: "Dashboard",       icon: ICONS.dashboard,       path: "/dashboard" },
    { text: "Attendance",      icon: ICONS.attendance,      path: "/attendance" },
    { text: "Employees",       icon: ICONS.employees,       path: "/employees" },
    { text: "My Leave",        icon: ICONS.leave,           path: "/leave" },
    { text: "Administration",  icon: ICONS.administration,  path: "/administration" },
    ...(loginType === "systemadmin"
      ? [{ text: "HR Copilot", icon: ICONS.hrcopilot, path: "/hr-copilot" }]
      : []),
  ];
  return items;
}

// ── Drawer content (used for both permanent and temporary) ────────────────────
function DrawerContent({ onClose, isMobile }) {
  const { logout, loginType, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const email = user?.email ?? "";
  const displayName = email.split("@")[0] || "Super Admin";
  const initials = displayName.slice(0, 2).toUpperCase();

  const navItems = getNavItems(loginType);

  const handleLogout = () => {
    logout();
    navigate({ to: "/login" });
  };

  const handleNav = () => {
    if (isMobile) onClose?.();
  };

  return (
    <div
      style={{
        width: DRAWER_WIDTH,
        height: "100%",
        display: "flex",
        flexDirection: "column",
        backgroundColor: "#ffffff",
        borderRight: "1px solid #e2e8f0",
        overflowY: "auto",
      }}
    >
      {/* ── Logo ─────────────────────────────────────────────────────────── */}
      <div
        style={{
          height: 72,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 24px",
          borderBottom: "1px solid #f1f5f9",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: 12,
              background: "#4f46e5",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: "0 4px 6px rgba(79,70,229,0.25)",
              flexShrink: 0,
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
              <path d="M8.5 11a4 4 0 1 0 0-8"/>
              <path d="M17 11l2 2 4-4"/>
            </svg>
          </div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 700, color: "#0f172a", lineHeight: 1.2 }}>
              AttendPro
            </div>
            <div style={{ fontSize: 11, color: "#94a3b8", fontWeight: 500 }}>
              Management Suite
            </div>
          </div>
        </div>
        {isMobile && (
          <button
            onClick={onClose}
            aria-label="Close menu"
            style={{
              border: "none",
              background: "none",
              cursor: "pointer",
              color: "#94a3b8",
              borderRadius: 8,
              padding: 6,
              display: "flex",
              alignItems: "center",
            }}
          >
            <Icon d={ICONS.close} />
          </button>
        )}
      </div>

      {/* ── Nav ──────────────────────────────────────────────────────────── */}
      <nav style={{ flex: 1, padding: "20px 16px 8px", overflowY: "auto" }}>
        <div
          style={{
            fontSize: 10,
            fontWeight: 700,
            textTransform: "uppercase",
            letterSpacing: "0.1em",
            color: "#94a3b8",
            padding: "0 12px",
            marginBottom: 8,
          }}
        >
          Workspace
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {navItems.map((item) => {
            const isActive =
              location.pathname === item.path ||
              (item.path !== "/" && location.pathname.startsWith(item.path));

            return (
              <Link
                key={item.text}
                to={item.path}
                onClick={handleNav}
                style={{ textDecoration: "none" }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 12,
                    padding: "10px 12px",
                    borderRadius: 10,
                    fontSize: 13,
                    fontWeight: isActive ? 600 : 500,
                    color: isActive ? "#4f46e5" : "#64748b",
                    backgroundColor: isActive ? "#eef2ff" : "transparent",
                    transition: "all 0.15s",
                    cursor: "pointer",
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) {
                      e.currentTarget.style.backgroundColor = "#f8fafc";
                      e.currentTarget.style.color = "#0f172a";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) {
                      e.currentTarget.style.backgroundColor = "transparent";
                      e.currentTarget.style.color = "#64748b";
                    }
                  }}
                >
                  <span style={{ color: isActive ? "#4f46e5" : "#94a3b8", flexShrink: 0, display: "flex" }}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      {item.icon}
                    </svg>
                  </span>
                  <span style={{ flex: 1 }}>{item.text}</span>
                  {isActive && (
                    <span
                      style={{
                        width: 6,
                        height: 6,
                        borderRadius: "50%",
                        background: "#4f46e5",
                        flexShrink: 0,
                      }}
                    />
                  )}
                </div>
              </Link>
            );
          })}
        </div>

        {/* Settings link */}
        <div style={{ marginTop: 8, borderTop: "1px solid #f1f5f9", paddingTop: 8 }}>
          <Link to="/settings" onClick={handleNav} style={{ textDecoration: "none" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "10px 12px",
                borderRadius: 10,
                fontSize: 13,
                fontWeight: location.pathname === "/settings" ? 600 : 500,
                color: location.pathname === "/settings" ? "#4f46e5" : "#64748b",
                backgroundColor: location.pathname === "/settings" ? "#eef2ff" : "transparent",
                transition: "all 0.15s",
                cursor: "pointer",
              }}
              onMouseEnter={(e) => {
                if (location.pathname !== "/settings") {
                  e.currentTarget.style.backgroundColor = "#f8fafc";
                  e.currentTarget.style.color = "#0f172a";
                }
              }}
              onMouseLeave={(e) => {
                if (location.pathname !== "/settings") {
                  e.currentTarget.style.backgroundColor = "transparent";
                  e.currentTarget.style.color = "#64748b";
                }
              }}
            >
              <span style={{ color: location.pathname === "/settings" ? "#4f46e5" : "#94a3b8", display: "flex", flexShrink: 0 }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  {ICONS.settings}
                </svg>
              </span>
              Settings
            </div>
          </Link>
        </div>
      </nav>

      {/* ── User + Logout ─────────────────────────────────────────────────── */}
      <div style={{ padding: "12px 16px 20px", borderTop: "1px solid #f1f5f9", flexShrink: 0 }}>
        {/* User card */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "10px 12px",
            borderRadius: 10,
            background: "#f8fafc",
            marginBottom: 4,
          }}
        >
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: "50%",
              background: "#eef2ff",
              color: "#4f46e5",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 12,
              fontWeight: 700,
              flexShrink: 0,
            }}
          >
            {initials}
          </div>
          <div style={{ minWidth: 0 }}>
            <div
              style={{
                fontSize: 12,
                fontWeight: 700,
                color: "#0f172a",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {displayName}
            </div>
            <div style={{ fontSize: 10, color: "#94a3b8" }}>
              {loginType === "systemadmin" ? "System Admin" : loginType === "admin" ? "Super Admin" : "Employee"}
            </div>
          </div>
        </div>

        {/* Logout */}
        <button
          onClick={handleLogout}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            gap: 12,
            padding: "10px 12px",
            borderRadius: 10,
            fontSize: 13,
            fontWeight: 500,
            color: "#64748b",
            background: "none",
            border: "none",
            cursor: "pointer",
            transition: "all 0.15s",
            textAlign: "left",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = "#fff1f2";
            e.currentTarget.style.color = "#e11d48";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = "transparent";
            e.currentTarget.style.color = "#64748b";
          }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            {ICONS.logout}
          </svg>
          Logout
        </button>
      </div>
    </div>
  );
}

// ── Public Sidebar export (drop-in replacement) ───────────────────────────────
export function Sidebar({ mobileOpen, handleDrawerToggle, isMobile }) {
  return (
    <>
      {/* Permanent sidebar for desktop */}
      <div
        style={{
          width: DRAWER_WIDTH,
          flexShrink: 0,
          display: isMobile ? "none" : "block",
          position: "sticky",
          top: 0,
          height: "100vh",
          overflowY: "auto",
        }}
      >
        <DrawerContent isMobile={false} />
      </div>

      {/* Overlay + temporary drawer for mobile */}
      {isMobile && (
        <>
          {mobileOpen && (
            <div
              onClick={handleDrawerToggle}
              style={{
                position: "fixed",
                inset: 0,
                zIndex: 1200,
                backgroundColor: "rgba(15,23,42,0.3)",
                backdropFilter: "blur(2px)",
              }}
              aria-label="Close menu"
            />
          )}
          <div
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              zIndex: 1300,
              height: "100vh",
              transform: mobileOpen ? "translateX(0)" : "translateX(-100%)",
              transition: "transform 0.28s cubic-bezier(0.4, 0, 0.2, 1)",
              boxShadow: mobileOpen ? "4px 0 24px rgba(15,23,42,0.12)" : "none",
            }}
          >
            <DrawerContent onClose={handleDrawerToggle} isMobile={true} />
          </div>
        </>
      )}
    </>
  );
}
