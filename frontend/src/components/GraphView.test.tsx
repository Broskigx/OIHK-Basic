import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { GraphView } from "./GraphView";

describe("GraphView empty states", () => {
  it("explains how to populate an empty investigation graph", () => {
    const markup = renderToStaticMarkup(<GraphView graph={{ nodes: [], edges: [] }} />);

    expect(markup).toContain("No entities yet");
    expect(markup).toContain("Add entity");
    expect(markup).toContain("import a CSV");
  });

  it("makes clear that filtering does not remove graph data", () => {
    const markup = renderToStaticMarkup(<GraphView graph={{ nodes: [], edges: [] }} typeFilter="email" />);

    expect(markup).toContain("No entities match this filter");
    expect(markup).toContain("Graph data was not removed");
  });
});
