import { describe, expect, it } from "vitest";
import { MAIN_NAVIGATION, parsePlatformHash, platformHash } from "./navigation";

describe("platform navigation", () => {
  it("round-trips a case-scoped workspace", () => {
    const hash = platformHash("evidence", "case-123");
    expect(hash).toBe("#/investigations/case-123/evidence");
    expect(parsePlatformHash(hash)).toEqual({ area: "evidence", caseId: "case-123" });
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

  it("presents the compatible tools route", () => {
    expect(MAIN_NAVIGATION.find((item) => item.id === "tools")?.label).toBe("Tools");
    expect(parsePlatformHash("#/investigations/case-123/tools")).toEqual({ area: "tools", caseId: "case-123" });
  });
});
