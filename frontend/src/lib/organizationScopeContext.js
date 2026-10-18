import { createContext } from "react";

// null default allows useOrganizationScope to detect usage outside the provider
// and throw a descriptive error instead of silently returning undefined.
export const OrganizationScopeContext = createContext(null);
