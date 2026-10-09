const domainCollator = new Intl.Collator(undefined, {
  numeric: true,
  sensitivity: "base",
});

/** Sort labels and identifiers naturally, so e.g. A2 precedes A10. */
export function sortOrganizationScopeValues(values) {
  return [...values].sort((left, right) =>
    domainCollator.compare(String(left), String(right)),
  );
}
