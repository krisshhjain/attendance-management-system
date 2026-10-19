let fallbackId = 0;

/** Generate a unique UI-only identifier without relying on weak randomness. */
export function createClientId() {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }

  fallbackId += 1;
  return `client-${Date.now()}-${fallbackId}`;
}
