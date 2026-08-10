import type { GraphRead } from "./types";

export const emptyGraph: GraphRead = { nodes: [], edges: [] };

export function score(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function shortDate(value?: string | null): string {
  if (!value) return "sin actividad";
  return new Intl.DateTimeFormat("es", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export function actionLabel(action: string): string {
  return action.replace(/\./g, " / ").replace(/_/g, " ");
}

/** Shorten a hash or UUID for display (e.g. "abc123...xyz789") */
export function shortHash(id: string): string {
  if (id.length <= 12) return id;
  return `${id.slice(0, 8)}...${id.slice(-4)}`;
}

/** Format a byte count for display (e.g. 1536 → "1.5 KB") */
export function formatByteSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** exponent;
  return `${value >= 10 || exponent === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[exponent]}`;
}
