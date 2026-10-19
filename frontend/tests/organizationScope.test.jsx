import { renderHook, act } from "@testing-library/react";
import { test, expect } from "vitest";
import {
  filterScopedRecords,
  getOrganizationScope,
  matchesOrganizationScope,
} from "../src/lib/organizationScopeUtils.js";
import { OrganizationScopeProvider } from "../src/lib/organizationScope.jsx";
import { useOrganizationScope } from "../src/lib/useOrganizationScope.js";

test("resolves scope fallbacks and matches organizational field aliases", () => {
  const scope = { brId: 1, sectionId: 2, subsectionId: 3 };
  expect(getOrganizationScope({ organizational_scope: scope })).toBe(scope);
  expect(getOrganizationScope({ scope })).toBe(scope);
  expect(getOrganizationScope(null)).toEqual({ assignedBRs: [] });
  expect(matchesOrganizationScope({ branch_id: 1, section: 2, subsection_id: 3 }, scope)).toBe(
    true,
  );
  expect(matchesOrganizationScope({ branch_id: 9, section: 2, subsection_id: 3 }, scope)).toBe(
    false,
  );
  expect(matchesOrganizationScope(null, scope)).toBe(true);
  expect(matchesOrganizationScope({ branch_id: 9 }, null)).toBe(true);
});

test("filters records within the selected scope and preserves unscoped inputs", () => {
  const records = [
    { id: 1, brId: 1, sectionId: 2 },
    { id: 2, brId: 2, sectionId: 2 },
  ];
  expect(filterScopedRecords(records, { brId: 1 }).map(({ id }) => id)).toEqual([1]);
  expect(filterScopedRecords(records, null)).toBe(records);
  expect(filterScopedRecords(null, { brId: 1 })).toBeNull();
});

test("provides selected scope state to consumer components", () => {
  const wrapper = ({ children }) => (
    <OrganizationScopeProvider>{children}</OrganizationScopeProvider>
  );
  const { result } = renderHook(() => useOrganizationScope(), { wrapper });
  const selectedScope = { brId: 4, sectionId: 6, subsectionId: null };

  expect(result.current.selectedScope).toEqual({ brId: null, sectionId: null, subsectionId: null });
  act(() => result.current.setSelectedScope(selectedScope));
  expect(result.current.selectedScope).toBe(selectedScope);
});

test("throws a clear error when scope hook is used outside its provider", () => {
  expect(() => renderHook(() => useOrganizationScope())).toThrow(
    "useOrganizationScope must be used within OrganizationScopeProvider",
  );
});
