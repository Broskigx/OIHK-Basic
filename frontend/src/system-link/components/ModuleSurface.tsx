import { useEffect, useMemo, useRef, useState } from "react";
import { getCase, listEvidence } from "../../api";
import type { LinkedSystemModule, SystemLinkCategory } from "../types";
import {
  buildModuleBridgeError,
  buildModuleBridgeResponse,
  isModuleBridgeRequest,
  moduleUiUrl,
  type ModuleBridgeOperation,
} from "../moduleSurface";

async function executeBridgeOperation(
  operation: ModuleBridgeOperation,
  payload: Record<string, unknown>,
): Promise<unknown> {
  switch (operation) {
    case "case.read": {
      const caseId = String(payload.caseId ?? "");
      if (!caseId) throw new Error("case.read requires a caseId");
      return getCase(caseId);
    }
    case "evidence.read": {
      const caseId = String(payload.caseId ?? "");
      if (!caseId) throw new Error("evidence.read requires a caseId");
      return listEvidence(caseId);
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
  }, [nonce]);

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
