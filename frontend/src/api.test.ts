import { beforeEach, describe, expect, it, vi } from "vitest";
import { clearToken, createCase, getToken, setToken } from "./api";

describe("token management", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("setToken stores the token in localStorage", () => {
    setToken("test-token-value");
    expect(localStorage.getItem("oihk.token")).toBe("test-token-value");
  });

  it("getToken retrieves the stored token", () => {
    localStorage.setItem("oihk.token", "my-token");
    expect(getToken()).toBe("my-token");
  });

  it("getToken returns null when no token is stored", () => {
    expect(getToken()).toBeNull();
  });

  it("clearToken removes the token from localStorage", () => {
    localStorage.setItem("oihk.token", "to-clear");
    clearToken();
    expect(localStorage.getItem("oihk.token")).toBeNull();
  });
});

describe("authenticated request protection", () => {
  it("echoes the backend CSRF cookie on mutations", async () => {
    document.cookie = "oihk_basic_csrf_token=csrf-test-token; path=/";
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("{}", { status: 200, headers: { "Content-Type": "application/json" } }),
    );

    await createCase({
      title: "Authorized review",
      summary: "",
      legal_basis: "Consent",
      scope_statement: "Bounded public-source review",
      priority: "normal",
      tags: [],
      notes: "",
    });

    const headers = new Headers(fetchMock.mock.calls[0]?.[1]?.headers);
    expect(headers.get("X-CSRF-Token")).toBe("csrf-test-token");
  });
});
