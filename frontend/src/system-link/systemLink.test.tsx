import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { buildModuleNavigation } from "./registry";
import { EvidenceLabCard } from "./modules/evidence-lab/EvidenceLabCard";
import { moduleActionsForState } from "./components/modulePowerModel";
import type { LinkedSystemModule } from "./types";

function moduleFixture(state: LinkedSystemModule["state"]): LinkedSystemModule {
  return {
    module_id: "oihk.evidence-lab",
    product_name: "OIHK Evidence Lab Basic",
    module_version: "0.1.0",
    protocol_version: "1.0",
    state,
    installed: true,
    linked: true,
    enabled: true,
    module_fingerprint: "a".repeat(64),
    package_sha256: "b".repeat(64),
    publisher: { key_id: "development", channel: "development" },
    frontend_entrypoint: "ui/index.js",
    granted_capabilities: ["ui.navigation.register"],
    requested_capabilities: ["ui.navigation.register"],
    categories: [{ id: "overview", route_id: "module:oihk.evidence-lab:overview", label: "Evidence Lab", icon: "microscope", case_scoped: true, order: 50, enabled: state === "READY" }],
    startup_policy: "manual",
    last_handshake_at: null,
    last_health_at: null,
    last_error_code: "",
    last_error_detail: "",
  };
}

describe("System Link module control plane", () => {
  it("renders linked and stopped Evidence Lab as OFF with Power On", () => {
    const html = renderToStaticMarkup(<EvidenceLabCard module={moduleFixture("LINKED_OFF")} busy={false} onAction={vi.fn()} />);
    expect(html).toContain("OFF");
    expect(html).toContain("Power On");
    expect(html).toContain("Secure pairing is preserved");
  });

  it("activates navigation only after authenticated READY", () => {
    expect(buildModuleNavigation([moduleFixture("STARTING")])).toEqual([]);
    expect(buildModuleNavigation([moduleFixture("ERROR")])).toEqual([]);
    expect(buildModuleNavigation([moduleFixture("READY")])).toEqual([
      expect.objectContaining({ id: "module:oihk.evidence-lab:overview", moduleId: "oihk.evidence-lab" }),
    ]);
  });

  it("keeps lifecycle actions bounded by state", () => {
    expect(moduleActionsForState("LINKED_OFF")).toContain("start");
    expect(moduleActionsForState("STARTING")).toEqual(["cancel"]);
    expect(moduleActionsForState("READY")).toEqual(["open", "stop", "restart"]);
    expect(moduleActionsForState("REVOKED")).not.toContain("start");
  });
});
