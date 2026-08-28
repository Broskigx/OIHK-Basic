import { AlertTriangle, ArrowRight, Download, FileCheck2, Puzzle, ShieldCheck, Trash2, User } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { deleteEvidence, downloadEvidenceManifest, listEvidence, verifyEvidence } from "../../api";
import { EmptyState } from "../../shared/ui/EmptyState";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";
import type { CustodyReport, EvidenceItem } from "../../types";
import {
  canVerify,
  chainVerdict,
  formatBytes,
  ingestedByLabel,
  summarizeRegister,
  verificationState,
} from "./custodyModel";

function date(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function Attribution({ ingestedBy }: { ingestedBy: string }) {
  const { kind, label } = ingestedByLabel(ingestedBy);
  return (
    <span className="platform-status" title={kind === "module" ? "Written by a linked module" : "Recorded by a person"}>
      {kind === "module" ? <Puzzle size={13} /> : <User size={13} />} {label}
    </span>
  );
}

export function CustodyRegisterView({
  caseId,
  custody,
  onOpenSystemLink,
  onOpenInvestigations,
  onRefresh,
}: {
  caseId: string;
  custody: CustodyReport | null;
  onOpenSystemLink: () => void;
  onOpenInvestigations: () => void;
  onRefresh: () => void;
}) {
  const [items, setItems] = useState<EvidenceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!caseId) {
      setItems([]);
      setLoading(false);
      return;
    }
    try {
      setItems(await listEvidence(caseId));
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not read the custody register");
    } finally {
      setLoading(false);
    }
  }, [caseId]);

  useEffect(() => {
    void load();
  }, [load]);

  const summary = useMemo(() => summarizeRegister(items), [items]);
  const chain = useMemo(() => chainVerdict(custody), [custody]);

  async function runVerification(item: EvidenceItem) {
    setBusy(item.id);
    setError("");
    try {
      await verifyEvidence(item.id);
      // Re-read rather than hold the verdict in component state: the backend
      // records it, so the row shows the same thing after a reload as it does
      // now. A result that only exists in this tab is a result that vanishes.
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Verification could not be completed");
    } finally {
      setBusy("");
    }
  }

  async function removeExhibit(item: EvidenceItem) {
    const held = item.held_by_basic
      ? "Its managed file will be deleted from this machine."
      : "The record will be removed; the linked module keeps its own copy.";
    if (!window.confirm(`Remove "${item.original_name}" from this investigation?\n\n${held}\n\nThis cannot be undone.`)) {
      return;
    }
    setBusy(item.id);
    setError("");
    try {
      await deleteEvidence(item.id);
      await load();
      onRefresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not remove the exhibit");
    } finally {
      setBusy("");
    }
  }

  async function exportManifest() {
    setError("");
    try {
      const blob = await downloadEvidenceManifest(caseId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `oihk-basic-custody-${caseId}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not export the custody manifest");
    }
  }

  if (!caseId) {
    return (
      <div className="platform-view">
        <WorkspaceHeader
          eyebrow="Chain of custody"
          title="Custody register"
          description="What this installation holds for an investigation, and whether it still matches its seals."
        />
        <EmptyState
          title="No active investigation"
          description="Choose an investigation to inspect its custody register."
          action={<button onClick={onOpenInvestigations}>View investigations</button>}
        />
      </div>
    );
  }

  return (
    <div className="platform-view">
      <WorkspaceHeader
        eyebrow="Chain of custody"
        title="Custody register"
        description="Evidence is acquired by a linked module. This is the record OIHK Basic keeps of it: what it holds, who put it there, and whether it still matches its seal."
        actions={
          items.length > 0 ? (
            <button type="button" onClick={() => void exportManifest()}>
              <Download size={14} /> Export manifest
            </button>
          ) : undefined
        }
      />

      {error && <div className="platform-inline-error" role="alert">{error}</div>}

      {summary.failingVerification > 0 && (
        <div className="platform-inline-error" role="alert">
          <AlertTriangle size={14} />{" "}
          {summary.failingVerification === 1
            ? "1 exhibit no longer matches its seal."
            : `${summary.failingVerification} exhibits no longer match their seals.`}{" "}
          A verdict is recorded against the exhibit and stands until it is checked again, unlike the chain summary
          below, which is recomputed on every load and covers the case as a whole.
        </div>
      )}

      <section className={`system-link-identity-strip custody-chain-${chain.tone}`}>
        {chain.tone === "warning" ? <AlertTriangle size={18} /> : <ShieldCheck size={18} />}
        <div>
          <strong>{chain.label}</strong>
          <span>{chain.detail}</span>
        </div>
        {summary.total > 0 && (
          <span>
            {summary.total} exhibit{summary.total === 1 ? "" : "s"} · {summary.heldByBasic} held here ·{" "}
            {summary.heldByModule} held by a module
            {summary.neverVerified > 0 ? ` · ${summary.neverVerified} never verified` : ""}
          </span>
        )}
      </section>

      {loading ? (
        <p className="platform-footnote">Reading the register…</p>
      ) : items.length === 0 ? (
        <EmptyState
          title="Nothing in custody yet"
          description="OIHK Basic does not acquire evidence itself. Link OIHK Evidence Lab, or another module granted evidence.write, and what it collects is sealed into this register."
          action={
            <button onClick={onOpenSystemLink}>
              Linked modules <ArrowRight size={14} />
            </button>
          }
        />
      ) : (
        <section className="platform-table-panel">
          <div className="platform-table-wrap">
            <table className="platform-table">
              <thead>
                <tr>
                  <th>Exhibit</th>
                  <th>SHA-256</th>
                  <th>Size</th>
                  <th>Held by</th>
                  <th>Recorded by</th>
                  <th>Last verified</th>
                  <th aria-label="Actions" />
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const verdict = verificationState(item);
                  return (
                    <tr key={item.id}>
                      <td>
                        <strong>{item.original_name}</strong>
                        <br />
                        <span className="platform-footnote">{item.mime_type}</span>
                      </td>
                      <td>
                        <code title={item.sha256}>{item.sha256.slice(0, 16)}…</code>
                        {verdict.kind !== "never" && (
                          <>
                            <br />
                            <span className={`platform-status ${verdict.kind === "intact" ? "success" : ""}`}>
                              {verdict.kind === "intact" ? <FileCheck2 size={13} /> : <AlertTriangle size={13} />}{" "}
                              {verdict.label}
                            </span>
                          </>
                        )}
                      </td>
                      <td>{formatBytes(item.size_bytes)}</td>
                      <td>
                        {item.held_by_basic ? (
                          <span className="platform-status">This machine</span>
                        ) : (
                          <span className="platform-status" title={item.original_reference}>
                            Linked module
                          </span>
                        )}
                      </td>
                      <td><Attribution ingestedBy={item.ingested_by} /></td>
                      <td>{item.verified_at ? date(item.verified_at) : <span className="platform-footnote">Never</span>}</td>
                      <td>
                        <div className="platform-row-actions">
                          <button
                            type="button"
                            onClick={() => void runVerification(item)}
                            disabled={!canVerify(item) || busy === item.id}
                            title={
                              canVerify(item)
                                ? "Re-hash the stored file and compare it against its seal"
                                : "This exhibit is held by a linked module; verify it there"
                            }
                          >
                            <FileCheck2 size={14} /> Verify
                          </button>
                          <button
                            type="button"
                            className="platform-danger"
                            onClick={() => void removeExhibit(item)}
                            disabled={busy === item.id}
                          >
                            <Trash2 size={14} /> Remove
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <p className="platform-footnote">
        No module can delete an exhibit. Removal is an operator action and is recorded in the audit trail under your
        name.
      </p>
    </div>
  );
}
