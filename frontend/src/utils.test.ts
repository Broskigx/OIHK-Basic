import { describe, it, expect } from "vitest";
import { emptyGraph, score, shortDate, actionLabel } from "./utils";

describe("emptyGraph", () => {
  it("should have empty nodes and edges", () => {
    expect(emptyGraph).toEqual({ nodes: [], edges: [] });
  });
});

describe("score", () => {
  it("should format a decimal as a percentage string", () => {
    expect(score(0.75)).toBe("75%");
    expect(score(1.0)).toBe("100%");
    expect(score(0.0)).toBe("0%");
  });
});

describe("shortDate", () => {
  it("should return 'sin actividad' for null/undefined", () => {
    expect(shortDate(null)).toBe("sin actividad");
    expect(shortDate(undefined)).toBe("sin actividad");
    expect(shortDate("")).toBe("sin actividad");
  });
});

describe("actionLabel", () => {
  it("should replace dots and underscores with spaces", () => {
    const result = actionLabel("case.created");
    expect(result).toContain("case");
    expect(result).toContain("created");
  });
});
