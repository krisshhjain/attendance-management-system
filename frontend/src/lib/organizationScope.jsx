import { createContext, useContext, useMemo, useState } from "react";

const OrganizationScopeContext = createContext(null);

export function getOrganizationScope(user) {
  return user?.organizational_scope || user?.scope || { assignedBRs: [] };
}

export function matchesOrganizationScope(record, selectedScope) {
  if (!record || !selectedScope) return true;
  const matches = (keys, selectedId) => !selectedId || keys.some((key) => record[key] === selectedId);

  return matches(["brId", "br_id", "branchId", "branch_id", "businessRegionId", "business_region_id"], selectedScope.brId)
    && matches(["sectionId", "section_id", "section", "sec", "SEC"], selectedScope.sectionId)
    && matches(["subsectionId", "subsection_id", "subsection", "sub", "SUB"], selectedScope.subsectionId);
}

export function filterScopedRecords(records, selectedScope) {
  if (!Array.isArray(records) || !selectedScope) return records;
  return records.filter((record) => matchesOrganizationScope(record, selectedScope));
}

export function OrganizationScopeProvider({ children }) {
  const [selectedScope, setSelectedScope] = useState({ brId: null, sectionId: null, subsectionId: null });
  const value = useMemo(() => ({ selectedScope, setSelectedScope }), [selectedScope]);

  return <OrganizationScopeContext.Provider value={value}>{children}</OrganizationScopeContext.Provider>;
}

export function useOrganizationScope() {
  const context = useContext(OrganizationScopeContext);
  if (!context) throw new Error("useOrganizationScope must be used within OrganizationScopeProvider");
  return context;
}