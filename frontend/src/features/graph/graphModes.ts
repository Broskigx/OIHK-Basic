import type { GraphRead } from "../../types";

export type GraphViewMode = "network" | "hierarchy" | "connections";

export type GraphViewOption = {
  id: GraphViewMode;
  label: string;
  description: string;
};

export type GraphLayoutPoint = {
  x: number;
  y: number;
  level: number;
};

export const GRAPH_VIEW_OPTIONS: GraphViewOption[] = [
  {
    id: "network",
    label: "Main graph",
    description: "Complete map of entities and relationships",
  },
  {
    id: "hierarchy",
    label: "Parent → child",
    description: "Directed hierarchy by level",
  },
  {
    id: "connections",
    label: "Connections",
    description: "Neighborhood and links for the active node",
  },
];

function orderedNodeIds(graph: GraphRead): string[] {
  return [...graph.nodes]
    .sort((left, right) => left.label.localeCompare(right.label) || left.id.localeCompare(right.id))
    .map((node) => node.id);
}

function graphDegree(graph: GraphRead): Map<string, number> {
  const degree = new Map(graph.nodes.map((node) => [node.id, 0]));
  graph.edges.forEach((edge) => {
    degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
    degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
  });
  return degree;
}

export function graphForView(graph: GraphRead, mode: GraphViewMode, focusNodeId = ""): GraphRead {
  if (mode !== "connections") return graph;

  const degree = graphDegree(graph);
  const focusIsConnected = Boolean(focusNodeId) && (degree.get(focusNodeId) ?? 0) > 0;
  const visibleIds = new Set<string>();

  if (focusIsConnected) {
    visibleIds.add(focusNodeId);
    graph.edges.forEach((edge) => {
      if (edge.source === focusNodeId) visibleIds.add(edge.target);
      if (edge.target === focusNodeId) visibleIds.add(edge.source);
    });
  } else {
    degree.forEach((count, nodeId) => {
      if (count > 0) visibleIds.add(nodeId);
    });
  }

  return {
    nodes: graph.nodes.filter((node) => visibleIds.has(node.id)),
    edges: graph.edges.filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target)),
  };
}

function highestDegreeNode(graph: GraphRead, candidates?: Set<string>): string | undefined {
  const degree = graphDegree(graph);
  return orderedNodeIds(graph)
    .filter((nodeId) => !candidates || candidates.has(nodeId))
    .sort((left, right) => (degree.get(right) ?? 0) - (degree.get(left) ?? 0))[0];
}

export function hierarchyLayout(graph: GraphRead): Record<string, GraphLayoutPoint> {
  const ids = orderedNodeIds(graph);
  const idSet = new Set(ids);
  const outgoing = new Map(ids.map((id) => [id, [] as string[]]));
  const indegree = new Map(ids.map((id) => [id, 0]));

  graph.edges.forEach((edge) => {
    if (!idSet.has(edge.source) || !idSet.has(edge.target)) return;
    outgoing.get(edge.source)?.push(edge.target);
    indegree.set(edge.target, (indegree.get(edge.target) ?? 0) + 1);
  });
  outgoing.forEach((targets) => targets.sort());

  const levels = new Map<string, number>();
  const queue: string[] = ids.filter((id) => (indegree.get(id) ?? 0) === 0);
  if (queue.length === 0 && ids.length > 0) queue.push(highestDegreeNode(graph) ?? ids[0]);
  queue.forEach((id) => levels.set(id, 0));

  for (let index = 0; index < queue.length; index += 1) {
    const nodeId = queue[index];
    const level = levels.get(nodeId) ?? 0;
    (outgoing.get(nodeId) ?? []).forEach((targetId) => {
      if (levels.has(targetId)) return;
      levels.set(targetId, level + 1);
      queue.push(targetId);
    });
  }

  const remaining = new Set(ids.filter((id) => !levels.has(id)));
  while (remaining.size > 0) {
    const root = highestDegreeNode(graph, remaining) ?? [...remaining][0];
    levels.set(root, 0);
    remaining.delete(root);
    const componentQueue = [root];
    for (let index = 0; index < componentQueue.length; index += 1) {
      const nodeId = componentQueue[index];
      const level = levels.get(nodeId) ?? 0;
      (outgoing.get(nodeId) ?? []).forEach((targetId) => {
        if (!remaining.has(targetId)) return;
        levels.set(targetId, level + 1);
        remaining.delete(targetId);
        componentQueue.push(targetId);
      });
    }
  }

  const rows = new Map<number, string[]>();
  ids.forEach((id) => {
    const level = levels.get(id) ?? 0;
    rows.set(level, [...(rows.get(level) ?? []), id]);
  });

  const points: Record<string, GraphLayoutPoint> = {};
  rows.forEach((rowIds, level) => {
    rowIds.forEach((id, index) => {
      points[id] = {
        x: (index - (rowIds.length - 1) / 2) * 14,
        y: level * 14,
        level,
      };
    });
  });
  return points;
}

export function connectionsLayout(graph: GraphRead, focusNodeId = ""): Record<string, GraphLayoutPoint> {
  const ids = orderedNodeIds(graph);
  if (ids.length === 0) return {};

  const idSet = new Set(ids);
  const neighbors = new Map(ids.map((id) => [id, new Set<string>()]));
  graph.edges.forEach((edge) => {
    if (!idSet.has(edge.source) || !idSet.has(edge.target)) return;
    neighbors.get(edge.source)?.add(edge.target);
    neighbors.get(edge.target)?.add(edge.source);
  });

  const center = idSet.has(focusNodeId) ? focusNodeId : (highestDegreeNode(graph) ?? ids[0]);
  const levels = new Map<string, number>([[center, 0]]);
  const queue = [center];
  for (let index = 0; index < queue.length; index += 1) {
    const nodeId = queue[index];
    const level = levels.get(nodeId) ?? 0;
    [...(neighbors.get(nodeId) ?? [])].sort().forEach((neighborId) => {
      if (levels.has(neighborId)) return;
      levels.set(neighborId, level + 1);
      queue.push(neighborId);
    });
  }

  const outerLevel = Math.max(0, ...levels.values()) + 1;
  ids.forEach((id) => {
    if (!levels.has(id)) levels.set(id, outerLevel);
  });

  const rings = new Map<number, string[]>();
  ids.forEach((id) => {
    const level = levels.get(id) ?? outerLevel;
    rings.set(level, [...(rings.get(level) ?? []), id]);
  });

  const points: Record<string, GraphLayoutPoint> = {
    [center]: { x: 0, y: 0, level: 0 },
  };
  rings.forEach((ringIds, level) => {
    if (level === 0) return;
    const radius = 13 * level;
    ringIds.forEach((id, index) => {
      const angle = -Math.PI / 2 + (index / ringIds.length) * Math.PI * 2;
      points[id] = {
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
        level,
      };
    });
  });
  return points;
}
