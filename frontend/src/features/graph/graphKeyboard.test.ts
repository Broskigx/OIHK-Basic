import { describe, expect, it } from "vitest";
import { resolveGraphShortcut } from "./graphKeyboard";

describe("resolveGraphShortcut", () => {
  it("maps graph navigation and history shortcuts", () => {
    expect(resolveGraphShortcut({ key: "f", ctrlKey: true })).toBe("focus-search");
    expect(resolveGraphShortcut({ key: "a", metaKey: true })).toBe("select-all");
    expect(resolveGraphShortcut({ key: "z", ctrlKey: true })).toBe("undo");
    expect(resolveGraphShortcut({ key: "z", ctrlKey: true, shiftKey: true })).toBe("redo");
    expect(resolveGraphShortcut({ key: "f" })).toBe("fit-view");
  });

  it("maps safe selection actions", () => {
    expect(resolveGraphShortcut({ key: "Escape" })).toBe("clear-selection");
    expect(resolveGraphShortcut({ key: "Delete" })).toBe("delete-selection");
  });

  it("does not capture shortcuts while the user is typing", () => {
    expect(resolveGraphShortcut({ key: "a", ctrlKey: true, editable: true })).toBeNull();
    expect(resolveGraphShortcut({ key: "Delete", editable: true })).toBeNull();
    expect(resolveGraphShortcut({ key: "Escape", editable: true })).toBe("dismiss-input");
  });
});
