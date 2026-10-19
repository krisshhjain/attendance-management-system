import { createContext } from "react";

// Default value is null so useAuth can detect when the hook is called outside
// of AuthProvider and throw a helpful error rather than returning undefined.
export const AuthContext = createContext(null);
