import type { CustodyReport, EvidenceItem } from "../../types";

export type RegisterSummary = {
  total: number;
  heldByBasic: number;
  heldByModule: number;
  neverVerified: number;
  failingVerification: number;
};

export type VerificationState = {
  kind: "never" | "intact" | "mismatch" | "unknown";
  label: string;
};

export type ChainVerdict = {
  tone: "positive" | "warning" | "neutral";
  label: string;
  detail: string;
};

export function summarizeRegister(items: readonly EvidenceItem[]): RegisterSummary {
  const heldByBasic = items.filter((item) => item.held_by_basic).length;
  return {
    total: items.length,
    heldByBasic,
    heldByModule: items.length - heldByBasic,
    neverVerified: items.filter((item) => !item.verified_at).length,
    failingVerification: items.filter((item) => item.last_verification_intact === false).length,
  };
}

/** The verdict on record for one exhibit.
 *
 * Four states, not two. "Never checked" is not "passed", and a row verified
 * before the verdict column existed has a timestamp with no outcome behind it
 * — reporting that as a pass would invent a result nobody produced.
 */
export function verificationState(item: EvidenceItem): VerificationState {
  if (!item.verified_at) return { kind: "never", label: "Never verified" };
  if (item.last_verification_intact === true) return { kind: "intact", label: "Matches its seal" };
  if (item.last_verification_intact === false) return { kind: "mismatch", label: "Does not match its seal" };
  return { kind: "unknown", label: "Checked before verdicts were recorded" };
}

export function chainVerdict(custody: CustodyReport | null): ChainVerdict {
  if (!custody) {
    return { tone: "neutral", label: "Chain status unavailable", detail: "The custody report has not loaded." };
  }
  if (!custody.intact) {
    return {
      tone: "warning",
      label: "Chain broken",
      detail: `Verification fails from seal ${custody.first_broken_sequence ?? "unknown"} onward.`,
    };
  }
  if (custody.sealed_count === 0) {
    // "Intact" across zero seals is true and useless. Reported as a positive
    // result it reads as a clean bill of health for a case nothing has been
    // sealed into, which is the opposite of what the operator should conclude.
    return { tone: "neutral", label: "Nothing sealed yet", detail: "No evidence has entered this case's chain." };
  }
  return {
    tone: "positive",
    label: "Chain intact",
    detail: `${custody.sealed_count} seal${custody.sealed_count === 1 ? "" : "s"} verify in sequence.`,
  };
}

/** Whether re-hashing this exhibit against its seal is meaningful.
 *
 * An imported record points at a linked module's own store, so Basic has no
 * bytes to hash. The route refuses it with 409 rather than answering, and the
 * button must not offer an action that cannot succeed.
 */
export function canVerify(item: EvidenceItem): boolean {
  return item.held_by_basic;
}

/** Split an audit actor into a module identity or a person. */
export function ingestedByLabel(ingestedBy: string): { kind: "module" | "person"; label: string } {
  if (ingestedBy.startsWith("module:")) {
    return { kind: "module", label: ingestedBy.slice("module:".length) || "unknown" };
  }
  return { kind: "person", label: ingestedBy || "unknown" };
}

const UNITS = ["B", "KB", "MB", "GB", "TB"] as const;

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < UNITS.length - 1) {
    value /= 1024;
    unit += 1;
  }
  // One decimal only when it says something: "1.5 KB" is useful, "1.0 KB" is noise.
  const rounded = Math.round(value * 10) / 10;
  return `${Number.isInteger(rounded) ? rounded : rounded.toFixed(1)} ${UNITS[unit]}`;
}
