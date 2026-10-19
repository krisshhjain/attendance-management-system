import assert from "node:assert/strict";
import { test } from "vitest";
import { createClientId } from "../src/lib/clientId.js";

test("client identifiers are unique for UI message keys", () => {
  assert.notEqual(createClientId(), createClientId());
});
