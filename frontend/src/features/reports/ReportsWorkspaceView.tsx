import {
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  Download,
  FileJson2,
  FileText,
  Loader2,
  Save,
  ShieldCheck,
  Sparkles,
  Trash2,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  approveReport,
  deleteReport,
  deleteReportTemplate,
  downloadReportDocument,
  generateAiReportDraft,
  generateReport,
  listReports,
  listReportTemplates,
  saveReportTemplate,
} from "../../api";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";
import type {
  CaseRead,
  CustodyReport,
  GraphRead,
  ReportDocument,
  ReportSection,
  ReportTemplate,
  SourceRead,
} from "../../types";

const SECTION_LABELS: Record<ReportSection, string> = {
  investigation: "Investigation profile",
  summary: "Executive summary",
  entities: "Entities",
  relationships: "Relationships",
  sources: "Sources and citations",
  evidence: "Managed evidence",
  notes: "Investigator notes",
  timeline: "Audit timeline",
  methodology: "Methodology",
  limitations: "Limitations",
};

const DEFAULT_SECTIONS = Object.keys(SECTION_LABELS) as ReportSection[];

function humanDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function ReportsWorkspaceView({
  activeCase,
  graph,
  sources,
  custody,
}: {
  activeCase: CaseRead;
  graph: GraphRead;
  sources: SourceRead[];
  custody: CustodyReport | null;
}) {
  const [reports, setReports] = useState<ReportDocument[]>([]);
  const [templates, setTemplates] = useState<ReportTemplate[]>([]);
  const [current, setCurrent] = useState<ReportDocument | null>(null);
  const [title, setTitle] = useState(`${activeCase.title} — Investigation report`);
  const [format, setFormat] = useState<"markdown" | "html" | "json">("markdown");
  const [sections, setSections] = useState<ReportSection[]>(DEFAULT_SECTIONS);
  const [methodology, setMethodology] = useState("Evidence-backed review of the records preserved in this investigation.");
  const [limitations, setLimitations] = useState("Verify identity, context, collection terms, and legal basis before external use.");
  const [templateName, setTemplateName] = useState("");
  const [aiFocus, setAiFocus] = useState("Summarize the strongest evidence, conflicts, gaps, and next verification steps.");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const refresh = async () => {
    const [reportRows, templateRows] = await Promise.all([listReports(activeCase.id), listReportTemplates()]);
    setReports(reportRows);
    setTemplates(templateRows);
    setCurrent((selected) => reportRows.find((item) => item.id === selected?.id) ?? reportRows[0] ?? null);
  };

  useEffect(() => {
    let active = true;
    setTitle(`${activeCase.title} — Investigation report`);
    setError("");
    Promise.all([listReports(activeCase.id), listReportTemplates()])
      .then(([reportRows, templateRows]) => {
        if (!active) return;
        setReports(reportRows);
        setTemplates(templateRows);
        setCurrent(reportRows[0] ?? null);
      })
      .catch((cause) => active && setError(cause instanceof Error ? cause.message : "Could not load reports"));
    return () => {
      active = false;
    };
  }, [activeCase.id, activeCase.title]);

  const selectedSet = useMemo(() => new Set(sections), [sections]);

  const toggleSection = (section: ReportSection) => {
    setSections((value) =>
      value.includes(section) ? value.filter((item) => item !== section) : [...value, section],
    );
  };

  const moveSection = (index: number, direction: -1 | 1) => {
    setSections((value) => {
      const target = index + direction;
      if (target < 0 || target >= value.length) return value;
      const copy = [...value];
      [copy[index], copy[target]] = [copy[target], copy[index]];
      return copy;
    });
  };

  const run = async (action: () => Promise<ReportDocument>) => {
    setBusy(true);
    setError("");
    try {
      const document = await action();
      setCurrent(document);
      await refresh();
      setCurrent(document);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Report operation failed");
    } finally {
      setBusy(false);
    }
  };

  const createReport = () => {
    if (!title.trim() || sections.length === 0) {
      setError("Add a report title and select at least one section.");
      return;
    }
    void run(() =>
      generateReport(activeCase.id, {
        title: title.trim(),
        format,
        sections,
        methodology,
        limitations,
      }),
    );
  };

  const createAiDraft = () =>
    void run(() => generateAiReportDraft(activeCase.id, { title: title.trim(), focus: aiFocus.trim() }));

  const exportCurrent = async () => {
    if (!current) return;
    setBusy(true);
    setError("");
    try {
      const blob = await downloadReportDocument(current.id);
      const suffix = { markdown: "md", html: "html", json: "json" }[current.format];
      const safeTitle = current.title.replace(/[^a-z0-9_-]+/gi, "_").replace(/^_+|_+$/g, "") || "report";
      downloadBlob(blob, `${safeTitle}.${suffix}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not export report");
    } finally {
      setBusy(false);
    }
  };

  const removeCurrent = async () => {
    if (!current || !window.confirm(`Delete “${current.title}”? This removes only the generated document.`)) return;
    setBusy(true);
    try {
      await deleteReport(current.id);
      setCurrent(null);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete report");
    } finally {
      setBusy(false);
    }
  };

  const createTemplate = async () => {
    if (!templateName.trim() || sections.length === 0) {
      setError("Name the template and select at least one section.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await saveReportTemplate({ name: templateName.trim(), format, sections, methodology, limitations });
      setTemplateName("");
      setTemplates(await listReportTemplates());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save template");
    } finally {
      setBusy(false);
    }
  };

  const applyTemplate = (template: ReportTemplate) => {
    setFormat(template.format);
    setSections(template.sections);
    setMethodology(template.methodology);
    setLimitations(template.limitations);
  };

  const removeTemplate = async (template: ReportTemplate) => {
    if (!window.confirm(`Delete template “${template.name}”?`)) return;
    setBusy(true);
    try {
      await deleteReportTemplate(template.id);
      setTemplates(await listReportTemplates());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not delete template");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="platform-view report-workspace">
      <WorkspaceHeader
        eyebrow="Evidence-backed output"
        title="Reports"
        description="Build persistent Markdown, safe HTML, or JSON reports from the records stored in this investigation."
        actions={
          <button type="button" className="platform-primary" onClick={createReport} disabled={busy || sections.length === 0}>
            {busy ? <Loader2 className="spin" size={15} /> : <FileText size={15} />}
            Generate report
          </button>
        }
      />

      {error && <div className="report-error" role="alert">{error}</div>}

      <div className="report-stats" aria-label="Report source statistics">
        <span><strong>{graph.nodes.length}</strong> entities</span>
        <span><strong>{graph.edges.length}</strong> relationships</span>
        <span><strong>{sources.length}</strong> sources</span>
        <span><strong>{custody?.sealed_count ?? 0}</strong> sealed items</span>
        <span className={custody?.intact ? "intact" : "review"}>
          <ShieldCheck size={13} /> {custody?.intact ? "Custody intact" : "Review custody"}
        </span>
      </div>

      <div className="report-layout">
        <aside className="report-builder">
          <section className="report-card">
            <div className="report-card-heading">
              <div><span className="platform-eyebrow">Builder</span><h2>Report structure</h2></div>
              <FileJson2 size={19} />
            </div>
            <label className="platform-field">
              <span>Title</span>
              <input value={title} maxLength={180} onChange={(event) => setTitle(event.target.value)} />
            </label>
            <label className="platform-field">
              <span>Format</span>
              <select value={format} onChange={(event) => setFormat(event.target.value as typeof format)}>
                <option value="markdown">Markdown</option>
                <option value="html">Safe HTML</option>
                <option value="json">Structured JSON</option>
              </select>
            </label>
            <div className="report-section-list">
              {sections.map((section, index) => (
                <div className="report-section-row" key={section}>
                  <label><input type="checkbox" checked onChange={() => toggleSection(section)} /> {SECTION_LABELS[section]}</label>
                  <span>
                    <button type="button" aria-label={`Move ${SECTION_LABELS[section]} up`} disabled={index === 0} onClick={() => moveSection(index, -1)}><ArrowUp size={13} /></button>
                    <button type="button" aria-label={`Move ${SECTION_LABELS[section]} down`} disabled={index === sections.length - 1} onClick={() => moveSection(index, 1)}><ArrowDown size={13} /></button>
                  </span>
                </div>
              ))}
              {DEFAULT_SECTIONS.filter((section) => !selectedSet.has(section)).map((section) => (
                <div className="report-section-row muted" key={section}>
                  <label><input type="checkbox" checked={false} onChange={() => toggleSection(section)} /> {SECTION_LABELS[section]}</label>
                </div>
              ))}
            </div>
            <label className="platform-field"><span>Methodology</span><textarea rows={3} value={methodology} onChange={(event) => setMethodology(event.target.value)} /></label>
            <label className="platform-field"><span>Limitations</span><textarea rows={3} value={limitations} onChange={(event) => setLimitations(event.target.value)} /></label>
            <button type="button" className="platform-primary platform-wide" disabled={busy || sections.length === 0} onClick={createReport}>
              <FileText size={15} /> Generate deterministic report
            </button>
          </section>

          <section className="report-card">
            <div className="report-card-heading"><div><span className="platform-eyebrow">Reusable</span><h2>Templates</h2></div><Save size={18} /></div>
            <div className="report-inline-form">
              <input placeholder="Template name" maxLength={100} value={templateName} onChange={(event) => setTemplateName(event.target.value)} />
              <button type="button" onClick={() => void createTemplate()} disabled={busy}>Save</button>
            </div>
            <div className="report-template-list">
              {templates.length === 0 && <p>No templates saved yet.</p>}
              {templates.map((template) => (
                <div key={template.id}>
                  <button type="button" onClick={() => applyTemplate(template)}><strong>{template.name}</strong><small>{template.format} · {template.sections.length} sections</small></button>
                  <button type="button" className="icon-danger" aria-label={`Delete ${template.name}`} onClick={() => void removeTemplate(template)}><Trash2 size={13} /></button>
                </div>
              ))}
            </div>
          </section>

          <section className="report-card ai-draft-card">
            <div className="report-card-heading"><div><span className="platform-eyebrow">Optional local AI</span><h2>Unverified draft</h2></div><Sparkles size={18} /></div>
            <p>Uses only your configured local model. Its output is always marked as a draft and must be reviewed.</p>
            <textarea rows={3} value={aiFocus} onChange={(event) => setAiFocus(event.target.value)} />
            <button type="button" onClick={createAiDraft} disabled={busy || !title.trim()}><Sparkles size={14} /> Create local AI draft</button>
          </section>
        </aside>

        <main className="report-preview-column">
          <section className="report-card report-preview-card">
            <div className="report-card-heading">
              <div><span className="platform-eyebrow">Preview</span><h2>{current?.title ?? "No report selected"}</h2></div>
              {current && <span className={`report-status ${current.status}`}>{current.status === "approved" ? <CheckCircle2 size={12} /> : null}{current.status}</span>}
            </div>
            {!current && <div className="report-empty"><FileText size={32} /><p>Generate a report or select one from history to preview it here.</p></div>}
            {current?.format === "html" && <iframe className="report-html-preview" sandbox="" title={`Preview of ${current.title}`} srcDoc={current.content} />}
            {current && current.format !== "html" && <pre className={`report-code-preview ${current.format}`}>{current.content}</pre>}
            {current && (
              <div className="report-preview-actions">
                {current.status !== "approved" && <button type="button" onClick={() => void run(() => approveReport(current.id))}><CheckCircle2 size={14} /> Approve reviewed report</button>}
                <button type="button" onClick={() => void exportCurrent()}><Download size={14} /> Export</button>
                <button type="button" className="icon-danger" onClick={() => void removeCurrent()}><Trash2 size={14} /> Delete</button>
              </div>
            )}
          </section>

          <section className="report-card report-history">
            <div className="report-card-heading"><div><span className="platform-eyebrow">Persistent history</span><h2>Generated documents</h2></div><span>{reports.length}</span></div>
            {reports.length === 0 && <p className="report-history-empty">Generated reports stay here until you remove them.</p>}
            {reports.map((report) => (
              <button type="button" className={current?.id === report.id ? "selected" : ""} key={report.id} onClick={() => setCurrent(report)}>
                <span className="report-format-icon">{report.format === "json" ? <FileJson2 size={15} /> : <FileText size={15} />}</span>
                <span><strong>{report.title}</strong><small>{humanDate(report.updated_at)} · {report.format}{report.ai_generated ? " · local AI draft" : ""}</small></span>
                <span className={`report-status ${report.status}`}>{report.status}</span>
              </button>
            ))}
          </section>
        </main>
      </div>
    </div>
  );
}
