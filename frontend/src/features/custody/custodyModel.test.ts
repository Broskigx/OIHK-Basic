import { describe, expect, it } from "vitest";
import type { CustodyReport, EvidenceItem } from "../../types";
import {
  canVerify,
  chainVerdict,
  formatBytes,
  ingestedByLabel,
  summarizeRegister,
  verificationState,
} from "./custodyModel";

function exhibit(overrides: Partial<EvidenceItem> = {}): EvidenceItem {
  return {
    id: "evidence-1",
    case_id: "case-1",
    source_id: "source-1",
    original_name: "exhibit.bin",
    mime_type: "application/octet-stream",
    size_bytes: 1024,
    sha256: "a".repeat(64),
    notes: "",
    tags: [],
    entity_ids: [],
    ingested_by: "module:oihk.evidence-lab",
    original_reference: "",
    held_by_basic: true,
    export_count: 0,
    created_at: "2026-08-27T00:00:00Z",
    updated_at: "2026-08-27T00:00:00Z",
    verified_at: null,
    last_verification_intact: null,
    ...overrides,
  };
}

describe("custody register summary", () => {
  it("separates what Basic holds from what it only records", () => {
    const summary = summarizeRegister([
      exhibit({ id: "a", held_by_basic: true }),
      exhibit({ id: "b", held_by_basic: false }),
      exhibit({ id: "c", held_by_basic: false }),
    ]);
    expect(summary).toEqual({
      total: 3,
      heldByBasic: 1,
      heldByModule: 2,
      neverVerified: 3,
      failingVerification: 0,
    });
  });

  it("counts only exhibits that have never been verified", () => {
    const summary = summarizeRegister([
      exhibit({ id: "a", verified_at: "2026-08-27T01:00:00Z" }),
      exhibit({ id: "b", verified_at: null }),
    ]);
    expect(summary.neverVerified).toBe(1);
  });

  it("reports an empty register without dividing by zero", () => {
    expect(summarizeRegister([])).toEqual({
      total: 0,
      heldByBasic: 0,
      heldByModule: 0,
      neverVerified: 0,
      failingVerification: 0,
    });
  });

  it("counts exhibits whose last check failed", () => {
    // The count has to come from the record, not from what happened to be
    // clicked in this session: a failed check must still be visible tomorrow.
    const summary = summarizeRegister([
      exhibit({ id: "a", verified_at: "2026-08-27T01:00:00Z", last_verification_intact: false }),
      exhibit({ id: "b", verified_at: "2026-08-27T01:00:00Z", last_verification_intact: true }),
      exhibit({ id: "c" }),
    ]);
    expect(summary.failingVerification).toBe(1);
    expect(summary.neverVerified).toBe(1);
  });
});

describe("verification state of one exhibit", () => {
  it("keeps never-checked distinct from checked-and-passed", () => {
    expect(verificationState(exhibit()).kind).toBe("never");
    expect(
      verificationState(exhibit({ verified_at: "2026-08-27T01:00:00Z", last_verification_intact: true })).kind,
    ).toBe("intact");
  });

  it("remembers a mismatch across a reload", () => {
    const state = verificationState(
      exhibit({ verified_at: "2026-08-27T01:00:00Z", last_verification_intact: false }),
    );
    expect(state.kind).toBe("mismatch");
    expect(state.label.toLowerCase()).toContain("not match");
  });

  it("treats a legacy row checked before verdicts were recorded as unknown", () => {
    // Migration 9 backfills nothing: a row verified under the old schema has a
    // timestamp and no verdict, and claiming it passed would be an invention.
    const state = verificationState(exhibit({ verified_at: "2026-08-27T01:00:00Z", last_verification_intact: null }));
    expect(state.kind).toBe("unknown");
  });
});

describe("chain verdict", () => {
  const chain = (over: Partial<CustodyReport> = {}): CustodyReport => ({
    case_id: "case-1",
    intact: true,
    sealed_count: 3,
    first_broken_sequence: null,
    entries: [],
    ...over,
  });

  it("names the sequence where the chain first broke", () => {
    const verdict = chainVerdict(chain({ intact: false, first_broken_sequence: 4 }));
    expect(verdict.tone).toBe("warning");
    expect(verdict.detail).toContain("4");
  });

  it("does not claim an intact chain when nothing is sealed yet", () => {
    // "Intact" over zero seals is technically true and practically misleading:
    // it reads as a positive result for a case nothing has been sealed into.
    const verdict = chainVerdict(chain({ sealed_count: 0 }));
    expect(verdict.tone).toBe("neutral");
  });

  it("confirms an intact chain that actually covers something", () => {
    expect(chainVerdict(chain()).tone).toBe("positive");
  });

  it("stays neutral while the report has not loaded", () => {
    expect(chainVerdict(null).tone).toBe("neutral");
  });
});

describe("what an operator may do with an exhibit", () => {
  it("offers verification only for bytes Basic actually holds", () => {
    // Re-hashing an exhibit the Lab holds would compare nothing against the
    // seal, and reporting that as a mismatch would read as tampering.
    expect(canVerify(exhibit({ held_by_basic: true }))).toBe(true);
    expect(canVerify(exhibit({ held_by_basic: false }))).toBe(false);
  });
});

describe("attribution", () => {
  it("distinguishes a linked module from a person", () => {
    expect(ingestedByLabel("module:oihk.evidence-lab")).toEqual({
      kind: "module",
      label: "oihk.evidence-lab",
    });
    expect(ingestedByLabel("analyst")).toEqual({ kind: "person", label: "analyst" });
  });

  it("does not mistake a username that merely contains the word", () => {
    expect(ingestedByLabel("module-operator").kind).toBe("person");
  });

  it("falls back rather than rendering an empty attribution", () => {
    expect(ingestedByLabel("").label).toBe("unknown");
  });
});

describe("byte formatting", () => {
  it("scales to a readable unit", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(999)).toBe("999 B");
    expect(formatBytes(1024)).toBe("1 KB");
    expect(formatBytes(1536)).toBe("1.5 KB");
    expect(formatBytes(1048576)).toBe("1 MB");
    expect(formatBytes(3 * 1024 ** 3)).toBe("3 GB");
  });

  it("does not produce NaN for a nonsense size", () => {
    expect(formatBytes(-1)).toBe("0 B");
    expect(formatBytes(Number.NaN)).toBe("0 B");
  });
});
