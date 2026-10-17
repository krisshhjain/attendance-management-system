/**
 * Returns the organizational scope attached to a user object.
 * Checks both `organizational_scope` and the legacy `scope` field to handle
 * responses from older API versions gracefully.
 *
 * @param {object} user - User object from AuthContext.
 * @returns {{ assignedBRs: string[] }} Scope object, defaulting to empty BRs.
 */
export function getOrganizationScope(user) {
  return user?.organizational_scope || user?.scope || { assignedBRs: [] };
}

/**
 * Returns true if `record` falls within the given `selectedScope`.
 *
 * Records in the backend use inconsistent field naming (camelCase vs snake_case
 * vs abbreviations), so each dimension is matched against multiple key aliases.
 * A null selectedId for any dimension means "no filter" and always matches.
 *
 * @param {object} record - A data record (attendance, employee, etc.)
 * @param {{ brId, sectionId, subsectionId }} selectedScope
 */
export function matchesOrganizationScope(record, selectedScope) {
  if (!record || !selectedScope) return true;
  const matches = (keys, selectedId) =>
    !selectedId || keys.some((key) => record[key] === selectedId);

  return (
    matches(
      // Multiple field name aliases handle inconsistent backend serialisation
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

/**
 * Filters an array of records to only those matching the selected scope.
 * Returns the original array unchanged if it is not an array or scope is null.
 *
 * @param {object[]} records
 * @param {{ brId, sectionId, subsectionId }} selectedScope
 */
export function filterScopedRecords(records, selectedScope) {
  if (!Array.isArray(records) || !selectedScope) return records;
  return records.filter((record) => matchesOrganizationScope(record, selectedScope));
}
