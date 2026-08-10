import { describe, expect, it } from "vitest";
import {
  buildModuleBridgeError,
  buildModuleBridgeResponse,
  isModuleBridgeRequest,
  moduleUiUrl,
  MODULE_BRIDGE_OPERATIONS,
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
