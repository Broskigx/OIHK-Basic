// Versioned bridge contract for the isolated System Link module UI surface.
//
// The module bundle runs inside a sandboxed iframe (opaque origin). The ONLY
// channel it has to the host is postMessage, and this module is the host-side
// gate: it validates the message shape, the per-surface nonce, the event
// source, and the operation allowlist before any Basic API call is made. The
// same operations are also enforced server-side by the regular API routes.

export const MODULE_BRIDGE_OPERATIONS = ["case.read", "evidence.read"] as const;

export type ModuleBridgeOperation = (typeof MODULE_BRIDGE_OPERATIONS)[number];

export type ModuleBridgeRequest = {
  type: "oihk-module-request";
  bridgeNonce: string;
  id: string;
  operation: ModuleBridgeOperation;
  payload: Record<string, unknown>;
};

export type ModuleBridgeResponse = {
  type: "oihk-module-response";
  id: string;
  ok: boolean;
  result?: unknown;
  error?: string;
};

export function isModuleBridgeRequest(value: unknown, nonce: string): value is ModuleBridgeRequest {
  if (typeof value !== "object" || value === null) return false;
  const message = value as Record<string, unknown>;
  if (message.type !== "oihk-module-request") return false;
  if (message.bridgeNonce !== nonce) return false;
  if (typeof message.id !== "string" || message.id.length === 0 || message.id.length > 128) return false;
  if (typeof message.operation !== "string") return false;
  if (!MODULE_BRIDGE_OPERATIONS.includes(message.operation as ModuleBridgeOperation)) return false;
  if (typeof message.payload !== "object" || message.payload === null) return false;
  return true;
}

export function buildModuleBridgeResponse(id: string, result: unknown): ModuleBridgeResponse {
  return { type: "oihk-module-response", id, ok: true, result };
}

export function buildModuleBridgeError(id: string, error: string): ModuleBridgeResponse {
  return { type: "oihk-module-response", id, ok: false, error };
}

export function moduleUiUrl(moduleId: string, entrypoint: string, nonce: string): string {
  const segments = entrypoint.split("/").map((segment) => encodeURIComponent(segment)).join("/");
  return `/system-link/modules/${encodeURIComponent(moduleId)}/ui/${segments}?bridge=${encodeURIComponent(nonce)}`;
}
