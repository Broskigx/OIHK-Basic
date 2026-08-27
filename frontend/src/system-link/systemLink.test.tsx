import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { buildModuleNavigation } from "./registry";
import { ModulePowerCard } from "./components/ModulePowerCard";
import { SystemLinkControlPlane } from "./components/SystemLinkControlPlane";
import { moduleActionsForState } from "./components/modulePowerModel";
import type { LinkedSystemModule } from "./types";

function moduleFixture(
  state: LinkedSystemModule["state"],
  moduleId = "oihk.evidence-lab",
  productName = "OIHK Evidence Lab Basic",
): LinkedSystemModule {
  return {
    module_id: moduleId,
    product_name: productName,
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
    categories: [{ id: "overview", route_id: `module:${moduleId}:overview`, label: "Overview", icon: "microscope", case_scoped: true, order: 50, enabled: state === "READY" }],
    startup_policy: "manual",
    last_handshake_at: null,
    last_health_at: null,
    last_error_code: "",
    last_error_detail: "",
  };
}

describe("System Link module control plane", () => {
  it("renders a linked and stopped module as OFF with Power On", () => {
    const html = renderToStaticMarkup(<ModulePowerCard module={moduleFixture("LINKED_OFF")} busy={false} onAction={vi.fn()} />);
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


function registryFixture(modules: LinkedSystemModule[]) {
  return {
    status: {
      protocol_version: "1.0",
      installation_public_key: "key",
      installation_fingerprint: "f".repeat(64),
      key_storage: "encrypted-file",
      modules,
    },
    pending: [],
    pairing: null,
    loading: false,
    busyModule: "",
    error: "",
    moduleNavigation: [],
    refresh: vi.fn(),
    runAction: vi.fn(),
    beginPairing: vi.fn(),
    approvePairing: vi.fn(),
  };
}

describe("control plane module list", () => {
  it("renders every linked module, not just the built-in one", () => {
    // The grid used to `find` a single hard-coded module id, so any other
    // module paired successfully on the backend and was then invisible here.
    const modules = [
      moduleFixture("READY"),
      moduleFixture("READY", "oihk.triage-suite", "OIHK Triage Suite"),
    ];
    const html = renderToStaticMarkup(
      <SystemLinkControlPlane registry={registryFixture(modules)} onNavigate={vi.fn()} />,
    );
    expect(html).toContain("OIHK Evidence Lab Basic");
    expect(html).toContain("OIHK Triage Suite");
  });

  it("shows a module that is not installed yet so it can be paired", () => {
    const notInstalled = { ...moduleFixture("NOT_INSTALLED"), installed: false, linked: false, enabled: false };
    const html = renderToStaticMarkup(
      <SystemLinkControlPlane registry={registryFixture([notInstalled])} onNavigate={vi.fn()} />,
    );
    expect(html).toContain("OIHK Evidence Lab Basic");
  });
});
