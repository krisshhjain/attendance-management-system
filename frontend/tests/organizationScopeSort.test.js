import assert from "node:assert/strict";
import test from "node:test";
import { sortOrganizationScopeValues } from "../src/components/dashboard/organizationScopeSort.js";

test("organization scopes sort numeric suffixes naturally", () => {
  assert.deepEqual(sortOrganizationScopeValues(["A10", "A2", "A1"]), ["A1", "A2", "A10"]);
});

test("organization scope sorting does not mutate its input", () => {
  const values = ["Section 10", "Section 2"];
  sortOrganizationScopeValues(values);
  assert.deepEqual(values, ["Section 10", "Section 2"]);
});
