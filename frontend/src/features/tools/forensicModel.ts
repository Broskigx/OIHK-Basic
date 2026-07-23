import type { ForensicCoreReport, ForensicIocMatch, SourceRead } from "../../types";

const FORENSIC_SOURCE_KINDS = new Set([
  "forensic_core",
  "forensic_media",
  "carved_artifact",
  "ioc_scan",
]);

export function forensicArtifactSources(sources: SourceRead[]): SourceRead[] {
  return sources
    .filter((source) => FORENSIC_SOURCE_KINDS.has(source.kind))
    .sort((left, right) => Date.parse(right.collected_at) - Date.parse(left.collected_at));
}

export function forensicSourceLabel(kind: string): string {
  const labels: Record<string, string> = {
    forensic_core: "Full analysis",
    forensic_media: "Media / steganography",
    carved_artifact: "Carved artifact",
    ioc_scan: "IOC scan",
  };
  return labels[kind] ?? kind.replace(/_/g, " ");
}

export function formatByteSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** exponent;
  return `${value >= 10 || exponent === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[exponent]}`;
}

export function groupForensicIocs(matches: ForensicIocMatch[]): Array<{ type: string; matches: ForensicIocMatch[] }> {
  const groups = new Map<string, ForensicIocMatch[]>();
  for (const match of matches) {
    const group = groups.get(match.type) ?? [];
    group.push(match);
    groups.set(match.type, group);
  }
  return [...groups.entries()]
    .map(([type, items]) => ({ type, matches: items.sort((a, b) => b.confidence - a.confidence) }))
    .sort((a, b) => b.matches.length - a.matches.length || a.type.localeCompare(b.type));
}

export function forensicReportCounts(report: ForensicCoreReport) {
  return {
    hashes: report.hashes.length,
    metadata: report.metadata?.fields.length ?? 0,
    indicators: report.iocs?.matches.length ?? 0,
    timeline: report.timeline_events.length,
    discrepancies: report.file_analysis?.discrepancies.length ?? 0,
  };
}
