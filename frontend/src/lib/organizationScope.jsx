import { useMemo, useState } from "react";
import { OrganizationScopeContext } from "./organizationScopeContext.js";

export function OrganizationScopeProvider({ children }) {
  const [selectedScope, setSelectedScope] = useState({
    brId: null,
    sectionId: null,
    subsectionId: null,
  });
  const value = useMemo(() => ({ selectedScope, setSelectedScope }), [selectedScope]);

  return (
    <OrganizationScopeContext.Provider value={value}>{children}</OrganizationScopeContext.Provider>
  );
}
