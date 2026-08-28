import { describe, expect, it } from "vitest";
import {
  buildModuleBridgeError,
  buildModuleBridgeResponse,
  isModuleBridgeRequest,
  moduleUiUrl,
  MODULE_BRIDGE_OPERATIONS,
  BRIDGE_OPERATION_CAPABILITY,
  bridgeOperationAllowed,
} from "./moduleSurface";

const NONCE = "surface-nonce-123";

describe("module surface bridge", () => {
  it("builds a same-origin surface URL with the per-surface nonce", () => {
    expect(moduleUiUrl("oihk.evidence-lab", "ui/index.js", NONCE)).toBe(
      "/system-link/modules/oihk.evidence-lab/ui/ui/index.js?bridge=surface-nonce-123",
    );
    expect(moduleUiUrl("oihk.evidence-lab", "assets/app.js", NONCE)).toContain("/ui/assets/app.js");
  });

  it("accepts a well-formed allowlisted request with the matching nonce", () => {
    const request = {
      type: "oihk-module-request",
      bridgeNonce: NONCE,
      id: "req-1",
      operation: "case.read",
      payload: { caseId: "case-1" },
    };
    expect(isModuleBridgeRequest(request, NONCE)).toBe(true);
    expect(MODULE_BRIDGE_OPERATIONS).toContain("evidence.read");
  });

  it("rejects requests with the wrong nonce, unknown operation, or bad shape", () => {
    const base = {
      type: "oihk-module-request",
      bridgeNonce: NONCE,
      id: "req-1",
      operation: "case.read",
      payload: { caseId: "case-1" },
    };
    expect(isModuleBridgeRequest({ ...base, bridgeNonce: "attacker-nonce" }, NONCE)).toBe(false);
    expect(isModuleBridgeRequest({ ...base, operation: "database.raw" }, NONCE)).toBe(false);
    expect(isModuleBridgeRequest({ ...base, type: "oihk-module-response" }, NONCE)).toBe(false);
    expect(isModuleBridgeRequest({ ...base, id: "" }, NONCE)).toBe(false);
    expect(isModuleBridgeRequest({ ...base, payload: "not-an-object" }, NONCE)).toBe(false);
    expect(isModuleBridgeRequest(null, NONCE)).toBe(false);
  });

  it("builds structured responses", () => {
    expect(buildModuleBridgeResponse("req-1", { ok: true })).toEqual({
      type: "oihk-module-response",
      id: "req-1",
      ok: true,
      result: { ok: true },
    });
    expect(buildModuleBridgeError("req-1", "denied")).toEqual({
      type: "oihk-module-response",
      id: "req-1",
      ok: false,
      error: "denied",
    });
  });
});

describe("bridge capability gating", () => {
  it("maps every bridge operation to the capability that authorises it", () => {
    // A bridge operation with no capability behind it would be reachable by
    // any linked module regardless of what the operator approved.
    for (const operation of MODULE_BRIDGE_OPERATIONS) {
      expect(BRIDGE_OPERATION_CAPABILITY[operation], `${operation} has no capability`).toBeTruthy();
    }
  });

  it("refuses an operation the module was never granted", () => {
    // The surface used to validate shape, nonce and event source, then call the
    // host API with the *operator's* session -- so a module approved for
    // navigation alone could still read every case and every exhibit.
    const navigationOnly = ["ui.navigation.register"];
    expect(bridgeOperationAllowed("case.read", navigationOnly)).toBe(false);
    expect(bridgeOperationAllowed("evidence.read", navigationOnly)).toBe(false);
    expect(bridgeOperationAllowed("entity.read", navigationOnly)).toBe(false);
  });

  it("allows exactly the operations covered by the module's grants", () => {
    const granted = ["ui.navigation.register", "case.read", "evidence.read"];
    expect(bridgeOperationAllowed("case.read", granted)).toBe(true);
    expect(bridgeOperationAllowed("evidence.read", granted)).toBe(true);
    expect(bridgeOperationAllowed("source.read", granted)).toBe(false);
    expect(bridgeOperationAllowed("case.list", granted)).toBe(false);
  });

  it("treats an empty grant list as granting nothing", () => {
    for (const operation of MODULE_BRIDGE_OPERATIONS) {
      expect(bridgeOperationAllowed(operation, [])).toBe(false);
    }
  });

  it("carries the reads a module surface needs", () => {
    expect([...MODULE_BRIDGE_OPERATIONS].sort()).toEqual([
      "case.list",
      "case.read",
      "entity.read",
      "evidence.read",
      "report.read",
      "source.read",
    ]);
  });
});
