import { describe, expect, it } from "vitest";

import { isSafeExternalHref, safeExternalHref } from "./safeUrl";

describe("safeExternalHref", () => {
  it("allows plain http and https URLs", () => {
    expect(safeExternalHref("https://example.com/path?q=1")).toBe("https://example.com/path?q=1");
    expect(safeExternalHref("http://example.com")).toBe("http://example.com/");
  });

  it.each([
    "javascript:alert(1)",
    "JavaScript:alert(1)",
    "  javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)",
    "file:///etc/passwd",
    "blob:https://example.com/uuid",
    "about:blank",
  ])("refuses the active or local scheme %s", (hostile) => {
    expect(safeExternalHref(hostile)).toBeUndefined();
    expect(isSafeExternalHref(hostile)).toBe(false);
  });

  it("refuses relative and malformed values rather than linking to them", () => {
    expect(safeExternalHref("/relative/path")).toBeUndefined();
    expect(safeExternalHref("not a url")).toBeUndefined();
    expect(safeExternalHref("")).toBeUndefined();
    expect(safeExternalHref(null)).toBeUndefined();
    expect(safeExternalHref(undefined)).toBeUndefined();
  });

  it("does not treat an embedded http substring as a safe scheme", () => {
    expect(safeExternalHref("javascript:void(location='http://evil.test')")).toBeUndefined();
  });
});
