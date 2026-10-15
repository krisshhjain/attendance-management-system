export function getOrganizationScope(user) {
  return user?.organizational_scope || user?.scope || { assignedBRs: [] };
}

export function matchesOrganizationScope(record, selectedScope) {
  if (!record || !selectedScope) return true;
  const matches = (keys, selectedId) =>
    !selectedId || keys.some((key) => record[key] === selectedId);

  return (
    matches(
      ["brId", "br_id", "branchId", "branch_id", "businessRegionId", "business_region_id"],
      selectedScope.brId,
    ) &&
    matches(["sectionId", "section_id", "section", "sec", "SEC"], selectedScope.sectionId) &&
    matches(
      ["subsectionId", "subsection_id", "subsection", "sub", "SUB"],
      selectedScope.subsectionId,
    )
  );
}

export function filterScopedRecords(records, selectedScope) {
  if (!Array.isArray(records) || !selectedScope) return records;
  return records.filter((record) => matchesOrganizationScope(record, selectedScope));
}
