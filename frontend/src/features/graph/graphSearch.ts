import type { GraphNode } from "../../types";

function searchableText(node: GraphNode): string {
  const properties = Object.entries(node.properties ?? {}).flatMap(([key, value]) => [key, String(value)]);
  return [node.label, node.value, node.id, node.type, node.notes, ...properties]
    .filter((value): value is string => Boolean(value))
    .join("\n")
    .toLocaleLowerCase();
}

export function searchGraphNodes(nodes: readonly GraphNode[], query: string): GraphNode[] {
  const normalized = query.trim().toLocaleLowerCase();
  if (!normalized) return [];
  return nodes
    .map((node) => {
      const label = node.label.toLocaleLowerCase();
      const value = node.value?.toLocaleLowerCase() ?? "";
      const id = node.id.toLocaleLowerCase();
      const text = searchableText(node);
      let rank = 9;
      if (label === normalized || value === normalized || id === normalized) rank = 0;
      else if (label.startsWith(normalized) || value.startsWith(normalized)) rank = 1;
      else if (label.includes(normalized) || value.includes(normalized)) rank = 2;
      else if (text.includes(normalized)) rank = 3;
      return { node, rank };
    })
    .filter((result) => result.rank < 9)
    .sort((left, right) => left.rank - right.rank || left.node.label.localeCompare(right.node.label))
    .map((result) => result.node);
}
