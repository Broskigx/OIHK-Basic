import { describe, expect, it, vi } from "vitest";
import { emptyGraph } from "../utils";

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => { store[key] = value; }),
    removeItem: vi.fn((key: string) => { delete store[key]; }),
    clear: vi.fn(() => { store = {}; }),
    get length() { return Object.keys(store).length; },
    key: vi.fn(() => null),
  };
})();

Object.defineProperty(globalThis, "localStorage", { value: localStorageMock });

// Mock the API module
vi.mock("../api", () => ({
  listCases: vi.fn(),
  getGraph: vi.fn(),
  listSources: vi.fn(),
  listTargets: vi.fn(),
  getCustody: vi.fn(),
  getCaseMonitor: vi.fn(),
  listAuditEvents: vi.fn(),
  getGraphAnalytics: vi.fn(),
  listTargetMemory: vi.fn(),
  listSearchRuns: vi.fn(),
  listSearchHits: vi.fn(),
  listTargetPhotos: vi.fn(),
  getToken: vi.fn(() => "mock-token"),
}));

import { getToken } from "../api";

describe("emptyGraph utility", () => {
  it("should be an empty graph with no nodes or edges", () => {
    expect(emptyGraph).toEqual({ nodes: [], edges: [] });
  });
});

describe("API function signatures", () => {
  it("getToken returns a string when mocked", () => {
    const token = getToken();
    expect(typeof token).toBe("string");
  });
});
