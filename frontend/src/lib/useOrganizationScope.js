import { useContext } from "react";
import { OrganizationScopeContext } from "./organizationScopeContext.js";

export function useOrganizationScope() {
  const context = useContext(OrganizationScopeContext);
  if (!context)
    throw new Error("useOrganizationScope must be used within OrganizationScopeProvider");
  return context;
}
