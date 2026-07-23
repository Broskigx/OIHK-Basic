import { describe, expect, it } from "vitest";
import type { ForensicCoreReport, ForensicIocMatch, SourceRead } from "../../types";
import {
  forensicArtifactSources,
  forensicReportCounts,
  forensicSourceLabel,
  formatByteSize,
  groupForensicIocs,
} from "./forensicModel";

function source(id: string, kind: string, collectedAt: string): SourceRead {
  return {
    id,
    case_id: "case-1",
    title: id,
    kind,
    url: null,
    citation: "local",
    license: "forensic-analysis",
    reliability: 0.85,
    robot_compliant: true,
    collected_at: collectedAt,
  };
}

describe("forensic workspace model", () => {
  it("keeps only persisted forensic artifacts and orders newest first", () => {
    const values = forensicArtifactSources([
      source("manual", "manual_text", "2026-01-03T00:00:00Z"),
      source("old", "forensic_core", "2026-01-01T00:00:00Z"),
      source("new", "carved_artifact", "2026-01-02T00:00:00Z"),
    ]);
    expect(values.map((item) => item.id)).toEqual(["new", "old"]);
  });

  it("groups indicators by type and orders stronger matches first", () => {
    const matches: ForensicIocMatch[] = [
      { type: "email", value: "a@b.test", display: "a@b.test", confidence: 0.7, offset: 2, context: "" },
      { type: "ipv4", value: "1.2.3.4", display: "1.2.3.4", confidence: 0.8, offset: 1, context: "" },
      { type: "email", value: "c@d.test", display: "c@d.test", confidence: 0.95, offset: 3, context: "" },
    ];
    const groups = groupForensicIocs(matches);
    expect(groups[0].type).toBe("email");
    expect(groups[0].matches.map((item) => item.value)).toEqual(["c@d.test", "a@b.test"]);
  });

  it("formats sizes and report counts without inventing values", () => {
    expect(formatByteSize(1536)).toBe("1.5 KB");
    expect(forensicSourceLabel("forensic_media")).toBe("Media / steganography");
    const report = {
      hashes: [{}, {}, {}],
      metadata: { fields: [{}, {}] },
      iocs: { matches: [{}] },
      timeline_events: [{}, {}],
      file_analysis: { discrepancies: [] },
    } as unknown as ForensicCoreReport;
    expect(forensicReportCounts(report)).toEqual({
      hashes: 3,
      metadata: 2,
      indicators: 1,
      timeline: 2,
      discrepancies: 0,
    });
  });
});
