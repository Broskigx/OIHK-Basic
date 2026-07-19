import React, { useState } from "react";
import type { SourceRead, CustodyReport, ForensicCoreReport, ForensicReport, CarveResult } from "../../types";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";
import { EmptyState } from "../../shared/ui/EmptyState";
import { analyzeForensics, analyzeForensicCore, getCustody, carveFile } from "../../api";

export function ToolsWorkspaceView({
  caseId, isAdmin, sources, custody, onRefresh, onOpenEvidence,
}: {
  caseId: string | null;
  isAdmin: boolean;
  sources: SourceRead[];
  custody: CustodyReport | null;
  onRefresh: () => void;
  onOpenEvidence: () => void;
}) {
  const [tab, setTab] = useState<"forensics" | "hashsets" | "carving">("forensics");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ForensicCoreReport | ForensicReport | null>(null);
  const [carveResult, setCarveResult] = useState<CarveResult | null>(null);
  const [error, setError] = useState("");

  const handleFileAnalysis = async (file: File) => {
    if (!caseId) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await analyzeForensicCore(caseId, file);
      setResult(res);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  };

  const handleCarve = async (file: File) => {
    if (!caseId) return;
    setLoading(true);
    setError("");
    setCarveResult(null);
    try {
      const res = await carveFile(caseId, file);
      setCarveResult(res);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Carving failed");
    } finally {
      setLoading(false);
    }
  };

  if (!caseId) {
    return (
      <div className="platform-view">
        <EmptyState title="No active case" description="Open an investigation to use forensic tools." />
      </div>
    );
  }

  return (
    <div className="platform-view">
      <WorkspaceHeader eyebrow="Forensic Analysis" title="Tools" description="File analysis, hash lookup, and data carving." />

      <div className="tabs">
        <button className={`tab ${tab === "forensics" ? "active" : ""}`} onClick={() => setTab("forensics")}>File Analysis</button>
        <button className={`tab ${tab === "carving" ? "active" : ""}`} onClick={() => setTab("carving")}>Carving</button>
      </div>

      {error && <div className="error-banner" style={{ marginBottom: "1rem" }}>{error}</div>}

      {tab === "forensics" && (
        <div className="card">
          <h3 style={{ marginBottom: "1rem" }}>File Analysis</h3>
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "1rem" }}>
            Upload a file for hashing, MIME detection, metadata extraction, and IOC scanning.
          </p>
          <input
            type="file"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFileAnalysis(f); }}
            style={{ marginBottom: "1rem" }}
          />
          {loading && <p>Analyzing...</p>}
          {result && (
            <div>
              <div className="stat-row" style={{ marginBottom: "1rem" }}>
                <div className="stat-card">
                  <div className="stat-label">Filename</div>
                  <div className="stat-value" style={{ fontSize: "1rem" }}>{result.filename}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">SHA256</div>
                  <div style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", wordBreak: "break-all" }}>
                    {"stored_sha256" in result ? result.stored_sha256 : result.sha256}
                  </div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Size</div>
                  <div className="stat-value" style={{ fontSize: "1rem" }}>{(result.size_bytes / 1024).toFixed(1)} KB</div>
                </div>
              </div>
              {"file_analysis" in result && result.file_analysis && (
                <div>
                  <h4 style={{ fontSize: "0.9rem", marginBottom: "0.5rem" }}>File Analysis</h4>
                  <table className="data-table">
                    <tbody>
                      <tr><td>MIME Type</td><td>{result.file_analysis.mime_type}</td></tr>
                      <tr><td>Detected</td><td>{result.file_analysis.detected_type} ({result.file_analysis.detected_label})</td></tr>
                      <tr><td>Entropy</td><td>{result.file_analysis.entropy}</td></tr>
                      {result.file_analysis.discrepancies.length > 0 && (
                        <tr><td>Discrepancies</td><td>{result.file_analysis.discrepancies.join(", ")}</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              )}
              {"iocs" in result && result.iocs && result.iocs.matches.length > 0 && (
                <div style={{ marginTop: "1rem" }}>
                  <h4 style={{ fontSize: "0.9rem", marginBottom: "0.5rem" }}>IOCs Found ({result.iocs.matches.length})</h4>
                  <table className="data-table">
                    <thead>
                      <tr><th>Type</th><th>Value</th><th>Confidence</th></tr>
                    </thead>
                    <tbody>
                      {result.iocs.matches.slice(0, 20).map((m, i) => (
                        <tr key={i}>
                          <td><span className="badge badge-warning">{m.type}</span></td>
                          <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.8rem" }}>{m.value}</td>
                          <td>{(m.confidence * 100).toFixed(0)}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {tab === "carving" && (
        <div className="card">
          <h3 style={{ marginBottom: "1rem" }}>Data Carving</h3>
          <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "1rem" }}>
            Extract embedded files (PNG, JPEG, ZIP) from binary data.
          </p>
          <input
            type="file"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) handleCarve(f); }}
            style={{ marginBottom: "1rem" }}
          />
          {loading && <p>Carving...</p>}
          {carveResult && (
            <div>
              <p>Found {carveResult.count} embedded artifacts.</p>
              {carveResult.artifacts.map((a, i) => (
                <div key={i} style={{ padding: "0.5rem", margin: "0.5rem 0", background: "var(--bg-tertiary)", borderRadius: "var(--radius-sm)" }}>
                  <div><strong>{a.label}</strong> ({a.carved_type})</div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                    Offset: {a.offset} · Size: {a.size} bytes · SHA256: {a.sha256.slice(0, 16)}…
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
