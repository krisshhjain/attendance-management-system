import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { apiRequest, tokenStore } from "./api.js";

const AuthContext = createContext(null);

// Helpers — always read/write localStorage directly so loginType
// is never out-of-sync with React state during re-renders
function getStoredLoginType() {
  return localStorage.getItem("loginType") || "employee";
}

function setStoredLoginType(type) {
  localStorage.setItem("loginType", type);
}

function clearStoredLoginType() {
  localStorage.removeItem("loginType");
}

export function AuthProvider({ children }) {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser]                       = useState(null);
  const [ready, setReady]                     = useState(false);
  // loginType state mirrors localStorage — initialised synchronously
  const [loginType, setLoginType]             = useState(getStoredLoginType);

  const fetchUser = useCallback(async () => {
    const data = await apiRequest("/auth/me/");
    setUser(data);
    return data;
  }, []);

  // Restore session on page load / refresh
  useEffect(() => {
    const init = async () => {
      if (tokenStore.access) {
        try {
          await fetchUser();
          // loginType is already correct from localStorage — just confirm auth
          setIsAuthenticated(true);
        } catch {
          tokenStore.clear();
          clearStoredLoginType();
          setLoginType("employee");
          setIsAuthenticated(false);
        }
      }
      setReady(true);
    };
    init();
  }, [fetchUser]);

  const login = useCallback(async (email, password, type = "employee") => {
    const data = await apiRequest("/auth/login/", {
      method: "POST",
      auth: false,
      body: { email, password },
    });
    if (!data?.access) throw new Error("Invalid email or password.");
    tokenStore.set(data.access, data.refresh);

    const userData = await fetchUser();

    if (type === "admin" && !userData.is_superuser) {
      // Roll back — not an admin
      tokenStore.clear();
      setUser(null);
      throw new Error("You do not have administrative privileges.");
    }

    // Persist BEFORE flipping isAuthenticated so RequireAuth never sees
    // a frame where user is set but loginType is stale
    setStoredLoginType(type);
    setLoginType(type);
    setIsAuthenticated(true);
  }, [fetchUser]);

  const logout = useCallback(() => {
    tokenStore.clear();
    clearStoredLoginType();
    setLoginType("employee");
    setUser(null);
    setIsAuthenticated(false);
  }, []);

  const value = useMemo(
    () => ({ isAuthenticated, ready, user, login, logout, loginType }),
    [isAuthenticated, ready, user, login, logout, loginType],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
