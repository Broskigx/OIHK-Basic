import { formatByteSize } from "../../utils";
import type { ForensicCoreReport, ForensicIocMatch, SourceRead } from "../../types";

export { formatByteSize };

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
