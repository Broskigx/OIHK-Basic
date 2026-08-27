// Versioned bridge contract for the isolated System Link module UI surface.
//
// The module bundle runs inside a sandboxed iframe (opaque origin). The ONLY
// channel it has to the host is postMessage, and this module is the host-side
// gate: it validates the message shape, the per-surface nonce, the event
// source, the operation allowlist, and — crucially — whether the module that
// owns this surface was actually granted the capability the operation needs.
//
// That last check is not redundant with the server. A bridge operation is
// served by calling Basic's own API with the *operator's* session, so the
// server sees an authorised human, not a module: it enforces what the operator
// may read, never what the module was approved for. Without the grant check
// here, a module approved for navigation alone could read every case and every
// exhibit in the installation simply by asking its own host surface for them.
//
// The bridge is deliberately read-only. A module's writes go through the
// signed, replay-protected module API in `system_link/module_api.py`, where
// they are attributed to the module and land in the audit trail under its
// name. Letting the iframe write here would launder a module's writes into
// the operator's identity, which is exactly what the audit trail exists to
// prevent.

export const MODULE_BRIDGE_OPERATIONS = [
  "case.read",
  "case.list",
  "evidence.read",
  "entity.read",
  "source.read",
  "report.read",
] as const;

export type ModuleBridgeOperation = (typeof MODULE_BRIDGE_OPERATIONS)[number];

/** The System Link capability a module must hold to invoke each operation. */
export const BRIDGE_OPERATION_CAPABILITY: Record<ModuleBridgeOperation, string> = {
  "case.read": "case.read",
  "case.list": "case.metadata.read",
  "evidence.read": "evidence.read",
  "entity.read": "entity.read",
  "source.read": "source.read",
  "report.read": "report.read",
};

/** Whether `grantedCapabilities` authorises `operation`. Fails closed. */
export function bridgeOperationAllowed(
  operation: ModuleBridgeOperation,
  grantedCapabilities: readonly string[],
): boolean {
  const required = BRIDGE_OPERATION_CAPABILITY[operation];
  return required !== undefined && grantedCapabilities.includes(required);
}

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
