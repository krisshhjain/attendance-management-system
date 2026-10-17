/**
 * lib/auth.jsx — Authentication context provider.
 *
 * Manages authentication state for the application:
 *  • Persists JWT tokens in localStorage under the keys defined in api.js.
 *  • Exposes { isAuthenticated, ready, user, login, logout, loginType, refreshUser }
 *    through AuthContext so any component can read/mutate auth state.
 *  • `ready` is false until the session-restore check (page load) completes;
 *    downstream components (e.g. RequireAuth) must wait for `ready` before
 *    acting on `isAuthenticated` to avoid a flash of the login screen.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { apiRequest, tokenStore } from "./api.js";
import { AuthContext } from "./authContext.js";

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
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  // loginType state mirrors localStorage — initialised synchronously
  const [loginType, setLoginType] = useState(getStoredLoginType);

  const fetchUser = useCallback(async () => {
    const data = await apiRequest("/auth/me/");
    setUser(data);
    return data;
  }, []);

  /**
   * Session restore on page load / refresh.
   *
   * If a stored access token exists, /auth/me/ is called to validate it and
   * populate the user object. On failure the token is cleared and the user is
   * treated as unauthenticated. setReady(true) is called in both branches so
   * RequireAuth knows the check has settled.
   */
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
    init().catch(() => {
      tokenStore.clear();
      clearStoredLoginType();
      setLoginType("employee");
      setIsAuthenticated(false);
      setReady(true);
    });
  }, [fetchUser]);

  /**
   * Authenticate the user.
   *
   * @param {string} email
   * @param {string} password
   * @param {"employee"|"admin"|"systemadmin"} type - Determines the login
   *   endpoint (systemadmin uses a dedicated route) and which layout is shown.
   *
   * Admin privilege check: after receiving tokens the server profile is fetched.
   * If the caller requested type="admin" but the profile lacks is_superuser, the
   * tokens are cleared and an error is thrown. This is a UI-level guard; the
   * backend enforces permissions on every privileged endpoint independently.
   *
   * setStoredLoginType is called BEFORE setIsAuthenticated to ensure that
   * RequireAuth never observes a frame where isAuthenticated=true but loginType
   * still holds a stale value from the previous session.
   */
  const login = useCallback(
    async (email, password, type = "employee") => {
      const loginEndpoint = type === "systemadmin" ? "/auth/systemadmin-login/" : "/auth/login/";
      const data = await apiRequest(loginEndpoint, {
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
    },
    [fetchUser],
  );

  const logout = useCallback(() => {
    tokenStore.clear();
    clearStoredLoginType();
    setLoginType("employee");
    setUser(null);
    setIsAuthenticated(false);
  }, []);

  /**
   * Exposed context value is memoised so consumers only re-render when one of
   * the listed dependencies actually changes, not on every AuthProvider render.
   * refreshUser (alias for fetchUser) is exposed so components can manually
   * re-sync user data after a profile update without triggering a full logout.
   */
  const value = useMemo(
    () => ({ isAuthenticated, ready, user, login, logout, loginType, refreshUser: fetchUser }),
    [isAuthenticated, ready, user, login, logout, loginType, fetchUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
