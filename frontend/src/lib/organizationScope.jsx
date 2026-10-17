import { useMemo, useState } from "react";
import { OrganizationScopeContext } from "./organizationScopeContext.js";

/**
 * OrganizationScopeProvider — shared scope filter state for admin views.
 *
 * Provides a selected scope ({ brId, sectionId, subsectionId }) and a setter
 * to all descendant components. Admin list views read this context to filter
 * records to the scope the admin has selected in the scope picker UI.
 *
 * All three IDs default to null, meaning "no filter applied" (show all records).
 * useMemo is used so consumers only re-render when the selectedScope object
 * reference changes, not on every parent re-render.
 */
export function OrganizationScopeProvider({ children }) {
  const [selectedScope, setSelectedScope] = useState({
    brId: null,       // Business Region ID filter
    sectionId: null,  // Section ID filter
    subsectionId: null, // Sub-section ID filter
  });
  const value = useMemo(() => ({ selectedScope, setSelectedScope }), [selectedScope]);

  return (
    <OrganizationScopeContext.Provider value={value}>{children}</OrganizationScopeContext.Provider>
  );
}
