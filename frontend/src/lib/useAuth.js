import { useContext } from "react";
import { AuthContext } from "./authContext.js";

/**
 * Hook that exposes the AuthContext value.
 *
 * Throws if called outside of AuthProvider, preventing silent failures where
 * components receive `undefined` instead of { isAuthenticated, ready, user,
 * login, logout, loginType, refreshUser }.
 */
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
