import { describe, expect, it } from "vitest";
import { GraphStore } from "./store";

describe("GraphStore selection", () => {
  it("preserves additive multi-selection and toggles an existing node", () => {
    const store = new GraphStore();

    store.setSelected("alpha");
    store.setSelected("beta", true);
    expect([...store.selectedNodeIds]).toEqual(["alpha", "beta"]);
    expect(store.selectedNodeId).toBe("beta");

    store.setSelected("beta", true);
    expect([...store.selectedNodeIds]).toEqual(["alpha"]);
    expect(store.selectedNodeId).toBe("alpha");
  });

  it("replaces the complete selection deterministically", () => {
    const store = new GraphStore();
    store.consumeDirty();

    store.setSelectedMany(["one", "two", "three"]);

    expect([...store.selectedNodeIds]).toEqual(["one", "two", "three"]);
    expect(store.selectedNodeId).toBe("one");
    expect(store.dirty.interaction).toBe(true);
  });
});
