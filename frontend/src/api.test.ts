import { beforeEach, describe, expect, it } from "vitest";
import { getToken, setToken, clearToken } from "./api";

describe("token management", () => {
  beforeEach(() => {
    localStorage.clear();
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
