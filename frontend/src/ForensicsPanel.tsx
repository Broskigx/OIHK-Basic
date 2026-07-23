import { FileSearch, ShieldAlert, Upload } from "lucide-react";
import { ChangeEvent, useState } from "react";

import { analyzeForensics } from "./api";
import type { ForensicReport } from "./types";

const VERDICT_LABEL: Record<string, string> = {
  clean: "Sin indicios",
  suspicious: "Sospechoso",
  high: "Probable dato oculto",
};

function renderMetaValue(value: unknown): string {
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "object" && value !== null) return JSON.stringify(value);
  return String(value);
}

export function ForensicsPanel({ caseId, onAnalyzed }: { caseId: string; onAnalyzed?: () => void }) {
  const [report, setReport] = useState<ForensicReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fileName, setFileName] = useState("");

  async function onFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setFileName(file.name);
    setBusy(true);
    setError("");
    setReport(null);
    try {
      const result = await analyzeForensics(caseId, file);
      setReport(result);
      onAnalyzed?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo analizar el archivo");
    } finally {
      setBusy(false);
      event.target.value = "";
    }
  }

  return (
    <div className="forensics-card">
      <div className="forensics-head">
        <FileSearch size={16} />
        <div>
          <strong>Forense / estego</strong>
          <span>Detecta datos ocultos y metadatos tecnicos</span>
        </div>
      </div>

      <label className="forensics-drop">
        <Upload size={18} />
        <span>{busy ? "Analizando..." : fileName || "Subir archivo para analizar"}</span>
        <input type="file" onChange={onFile} disabled={busy} hidden />
      </label>

      {error && <div className="forensics-error">{error}</div>}

      {report && (
        <div className="forensics-report">
          <div className={`forensics-verdict ${report.verdict}`}>
            <ShieldAlert size={15} />
            <strong>{VERDICT_LABEL[report.verdict] ?? report.verdict}</strong>
            <span>{report.suspicion_score}/100</span>
          </div>
          <div className="forensics-meter">
            <i style={{ width: `${report.suspicion_score}%` }} className={report.verdict} />
          </div>

          <dl className="forensics-facts">
            <div>
              <dt>Tipo real</dt>
              <dd>{report.detected_label}</dd>
            </div>
            {report.type_mismatch && (
              <div>
                <dt>Extension</dt>
                <dd className="warn">no coincide ({report.claimed_type})</dd>
              </div>
            )}
            <div>
              <dt>Entropia</dt>
              <dd>
                {report.entropy} (max {report.max_window_entropy})
              </dd>
            </div>
            {report.trailing_bytes > 0 && (
              <div>
                <dt>Datos anexados</dt>
                <dd className="warn">{report.trailing_bytes} bytes</dd>
              </div>
            )}
            <div>
              <dt>SHA-256</dt>
              <dd className="mono">{report.sha256.slice(0, 24)}...</dd>
            </div>
          </dl>

          {Object.keys(report.media_metadata ?? {}).length > 0 && (
            <div className="forensics-metadata">
              {Object.entries(report.media_metadata)
                .slice(0, 8)
                .map(([key, value]) => (
                  <div key={key}>
                    <span>{key}</span>
                    <code>{renderMetaValue(value)}</code>
                  </div>
                ))}
            </div>
          )}

          <ul className="forensics-findings">
            {report.findings.map((finding, index) => (
              <li key={index} className={finding.severity}>
                <span className="tag">{finding.severity}</span>
                {finding.detail}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
