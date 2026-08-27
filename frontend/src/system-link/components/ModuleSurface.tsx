import { useEffect, useMemo, useRef, useState } from "react";
import { getCase, getGraph, listCases, listEvidence, listReports, listSources } from "../../api";
import type { LinkedSystemModule, SystemLinkCategory } from "../types";
import {
  bridgeOperationAllowed,
  buildModuleBridgeError,
  buildModuleBridgeResponse,
  isModuleBridgeRequest,
  moduleUiUrl,
  type ModuleBridgeOperation,
} from "../moduleSurface";

function requireCaseId(payload: Record<string, unknown>, operation: string): string {
  const caseId = String(payload.caseId ?? "");
  if (!caseId) throw new Error(`${operation} requires a caseId`);
  return caseId;
}

async function executeBridgeOperation(
  operation: ModuleBridgeOperation,
  payload: Record<string, unknown>,
): Promise<unknown> {
  switch (operation) {
    case "case.read":
      return getCase(requireCaseId(payload, operation));
    case "case.list":
      return listCases();
    case "evidence.read":
      return listEvidence(requireCaseId(payload, operation));
    case "entity.read":
      return getGraph(requireCaseId(payload, operation));
    case "source.read":
      return listSources(requireCaseId(payload, operation));
    case "report.read":
      return listReports(requireCaseId(payload, operation));
    default: {
      // Exhaustiveness guard: adding an operation to MODULE_BRIDGE_OPERATIONS
      // without a case here is a compile error rather than a silent undefined
      // handed back to the module as a successful result.
      const unreachable: never = operation;
      throw new Error(`Unhandled bridge operation: ${String(unreachable)}`);
    }
  }
}

export function ModuleSurface({
  module,
  category,
  activeCaseId,
}: {
  module: LinkedSystemModule;
  category: SystemLinkCategory;
  activeCaseId?: string;
}) {
  const [nonce] = useState(() =>
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`,
  );
  const frameRef = useRef<HTMLIFrameElement>(null);
  const entrypoint = module.frontend_entrypoint || "ui/index.js";
  const src = useMemo(() => moduleUiUrl(module.module_id, entrypoint, nonce), [module.module_id, entrypoint, nonce]);

  useEffect(() => {
    function handleMessage(event: MessageEvent) {
      // Only the exact frame we rendered may talk to the bridge.
      if (event.source !== frameRef.current?.contentWindow) return;
      if (!isModuleBridgeRequest(event.data, nonce)) return;
      const request = event.data;
      // The operation is served with the operator's session, so the server
      // will happily answer it. What the operator approved for *this module*
      // is only known here.
      if (!bridgeOperationAllowed(request.operation, module.granted_capabilities)) {
        frameRef.current?.contentWindow?.postMessage(
          buildModuleBridgeError(
            request.id,
            `Capability '${request.operation}' was not granted to ${module.module_id}`,
          ),
          "*",
        );
        return;
      }
      void executeBridgeOperation(request.operation, request.payload)
        .then((result) => {
          frameRef.current?.contentWindow?.postMessage(buildModuleBridgeResponse(request.id, result), "*");
        })
        .catch((cause: unknown) => {
          const detail = cause instanceof Error ? cause.message : "Module bridge operation failed";
          frameRef.current?.contentWindow?.postMessage(buildModuleBridgeError(request.id, detail), "*");
        });
    }
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [nonce, module.granted_capabilities, module.module_id]);

  return (
    <div className="system-link-module-surface">
      <iframe
        ref={frameRef}
        sandbox="allow-scripts"
        src={src}
        title={`${module.product_name} · ${category.label}`}
        className="system-link-module-frame"
      />
      {activeCaseId ? (
        <span className="platform-eyebrow system-link-module-case">Active case: {activeCaseId}</span>
      ) : null}
    </div>
  );
}
