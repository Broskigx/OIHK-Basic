import { createElement } from "react";
import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { GraphView } from "./GraphView";

const emptyGraph = { nodes: [], edges: [] };

describe("GraphView empty states", () => {
  it("guides analysts to add or import the first entity", () => {
    const markup = renderToString(createElement(GraphView, { graph: emptyGraph }));

    expect(markup).toContain("Start with an entity");
    expect(markup).toContain("Add an entity above or import data");
    expect(markup).toContain('class="platform-empty-state graph-empty-state"');
    expect(markup.toLowerCase()).not.toContain("graph ready");
  });

  it("explains empty filtered and connections views", () => {
    const filteredMarkup = renderToString(createElement(GraphView, {
      graph: emptyGraph,
      typeFilter: "email",
    }));
    const connectionsMarkup = renderToString(createElement(GraphView, {
      graph: emptyGraph,
      viewMode: "connections",
    }));

    expect(filteredMarkup).toContain("No matching entities");
    expect(filteredMarkup).toContain("Adjust or clear the active type filter");
    expect(connectionsMarkup).toContain("Choose an entity");
    expect(connectionsMarkup).toContain("Select an entity to inspect its direct connections");
  });
});
