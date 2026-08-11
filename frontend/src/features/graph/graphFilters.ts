import type { GraphRead } from "../../types";

export type GraphSourceFilter = "all" | "with-sources" | "without-sources";

export function filterGraphForView(
  graph: GraphRead,
  typeFilter: string,
  sourceFilter: GraphSourceFilter,
): GraphRead {
  if (typeFilter === "all" && sourceFilter === "all") return graph;

  const nodes = graph.nodes.filter((node) => {
    const matchesType = typeFilter === "all" || node.type === typeFilter;
    const hasSources = node.source_ids.length > 0;
    const matchesSource = sourceFilter === "all"
      || (sourceFilter === "with-sources" ? hasSources : !hasSources);
    return matchesType && matchesSource;
  });
  const visibleIds = new Set(nodes.map((node) => node.id));
  return {
    nodes,
    edges: graph.edges.filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target)),
  };
}
