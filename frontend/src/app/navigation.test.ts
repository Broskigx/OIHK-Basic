import { describe, expect, it } from "vitest";
import {
  CORE_NAVIGATION,
  createModuleRouteId,
  parsePlatformHash,
  platformHash,
  type NavigationItem,
} from "./navigation";

describe("platform navigation", () => {
  it("round-trips a case-scoped workspace", () => {
    const hash = platformHash("graph", "case-123");
    expect(hash).toBe("#/investigations/case-123/graph");
    expect(parsePlatformHash(hash)).toEqual({ area: "graph", caseId: "case-123" });
  });

  it("maps investigation overview to the investigations area", () => {
    expect(parsePlatformHash("#/investigations/abc/overview")).toEqual({
      area: "investigations",
      caseId: "abc",
    });
  });

  it("falls back safely for unknown routes", () => {
    expect(parsePlatformHash("#/not-real")).toEqual({ area: "dashboard", caseId: "" });
  });

  it("no longer routes to the removed Evidence Lab workspaces", () => {
    // Evidence Lab is installed separately and reached through System Link, so
    // a stale bookmark to its old in-app route must not resolve to a blank
    // screen -- it resolves to nothing and the shell falls back.
    const ids = CORE_NAVIGATION.map((item) => String(item.id));
    expect(ids).not.toContain("evidence");
    expect(ids).not.toContain("tools");
    // A bookmark saved before the split must land somewhere real rather than
    // on a route the shell has no case for: both fall back to the case itself.
    expect(parsePlatformHash("#/investigations/case-123/evidence")).toEqual({
      area: "investigations",
      caseId: "case-123",
    });
    expect(parsePlatformHash("#/investigations/case-123/tools")).toEqual({
      area: "investigations",
      caseId: "case-123",
    });
  });

  it("keeps the agent out of page navigation and safely retires legacy Copilot links", () => {
    expect(CORE_NAVIGATION.some((item) => String(item.id) === "copilot")).toBe(false);
    expect(parsePlatformHash("#/investigations/case-123/copilot")).toEqual({
      area: "investigations",
      caseId: "case-123",
    });
  });

  it("round-trips only a registered namespaced module route", () => {
    const route = createModuleRouteId("oihk.evidence-lab", "overview");
    const navigation: NavigationItem[] = [{ id: route, label: "Evidence Lab", caseScoped: true }];
    const hash = platformHash(route, "case-123");
    expect(hash).toBe("#/investigations/case-123/modules/oihk.evidence-lab/overview");
    expect(parsePlatformHash(hash, navigation)).toEqual({ area: route, caseId: "case-123" });
    expect(parsePlatformHash(hash)).toEqual({ area: "investigations", caseId: "case-123" });
  });

  it("rejects malformed module ids and cannot override a core route", () => {
    expect(() => createModuleRouteId("dashboard", "../settings")).toThrow("Invalid namespaced");
    expect(parsePlatformHash("#/modules/dashboard/settings", [])).toEqual({ area: "dashboard", caseId: "" });
  });
});
