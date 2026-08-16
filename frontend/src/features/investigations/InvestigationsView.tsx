import {
  Archive,
  ArrowRight,
  BriefcaseBusiness,
  Clock3,
  Copy,
  Download,
  FileCheck,
  FileUp,
  Pencil,
  Plus,
  RotateCcw,
  Search,
  Shield,
  Trash2,
} from "lucide-react";
import { ChangeEvent, useMemo, useRef, useState } from "react";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";
import type { CaseMonitor, CaseRead, InvestigationDraft } from "../../types";
import { NewInvestigationDialog } from "./NewInvestigationDialog";

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function draftFromCase(item: CaseRead): InvestigationDraft {
  return {
    title: item.title,
    summary: item.summary,
    legal_basis: item.legal_basis,
    scope_statement: item.scope_statement,
    priority: item.priority,
    tags: item.tags,
    notes: item.notes,
  };
}

export function InvestigationsView({
  cases,
  activeCase,
  monitor,
  loading,
  canRerun,
  onOpenCase,
  onNewCase,
  onRunAgain,
  onOpenWorkspace,
  onEdit,
  onDuplicate,
  onSetStatus,
  onDelete,
  onExport,
  onImport,
}: {
  cases: CaseRead[];
  activeCase?: CaseRead;
  monitor: CaseMonitor | null;
  loading: boolean;
  canRerun: boolean;
  onOpenCase: (caseId: string) => void;
  onNewCase: () => void;
  onRunAgain: () => void;
  onOpenWorkspace: () => void;
  onEdit: (caseId: string, draft: InvestigationDraft) => Promise<void>;
  onDuplicate: (caseId: string) => Promise<void>;
  onSetStatus: (caseId: string, status: "active" | "archived") => Promise<void>;
  onDelete: (caseId: string) => Promise<void>;
  onExport: (caseId: string, title: string) => Promise<void>;
  onImport: (document: unknown) => Promise<void>;
}) {
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [priorityFilter, setPriorityFilter] = useState("all");
  const [sort, setSort] = useState<"updated" | "name" | "priority">("updated");
  const [editing, setEditing] = useState<CaseRead | null>(null);
  const [importError, setImportError] = useState("");
  const importRef = useRef<HTMLInputElement>(null);

  const filteredCases = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    const rank = { critical: 4, high: 3, normal: 2, low: 1 };
    return cases
      .filter((item) => {
        const matchesText = !query || [item.title, item.summary, item.scope_statement, ...item.tags].some((value) => value.toLowerCase().includes(query));
        return matchesText && (statusFilter === "all" || item.status === statusFilter) && (priorityFilter === "all" || item.priority === priorityFilter);
      })
      .sort((a, b) => sort === "name" ? a.title.localeCompare(b.title) : sort === "priority" ? rank[b.priority] - rank[a.priority] : new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
  }, [cases, priorityFilter, searchQuery, sort, statusFilter]);

  async function importFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setImportError("");
    if (file.size > 10 * 1024 * 1024) {
      setImportError("Investigation imports are limited to 10 MB.");
      return;
    }
    try {
      await onImport(JSON.parse(await file.text()) as unknown);
    } catch (cause) {
      setImportError(cause instanceof Error ? cause.message : "The selected file is not valid JSON.");
    }
  }

  return (
    <div className="platform-view">
      <WorkspaceHeader
        eyebrow="Investigations"
        title="Investigations"
        description="Create, organize, export, and archive private investigation workspaces stored on this device."
        actions={<>
          <input ref={importRef} type="file" accept="application/json,.json" hidden onChange={(event) => void importFile(event)} />
          <button type="button" onClick={() => importRef.current?.click()} disabled={loading}><FileUp size={14} /> Import</button>
          <button type="button" className="platform-primary-btn" onClick={onNewCase} disabled={loading}><Plus size={14} /> New investigation</button>
        </>}
      />

      {importError && <div className="platform-inline-error" role="alert">{importError}</div>}

      {cases.length === 0 ? (
        <div className="platform-investigations-empty">
          <div className="platform-investigations-empty-panel">
            <div className="platform-investigations-empty-icon"><BriefcaseBusiness size={32} /></div>
            <h2>No investigations yet</h2>
            <p>Create a local, authorized workspace to organize entities, evidence, relationships, queries, and analysis.</p>
            <button type="button" className="platform-primary-btn" onClick={onNewCase}><Plus size={14} /> Create investigation</button>
          </div>
          <div className="platform-investigations-features">
            <div className="platform-feature-card"><Shield size={16} /><strong>Local-first storage</strong><span>Case data stays under your control</span></div>
            <div className="platform-feature-card"><BriefcaseBusiness size={16} /><strong>Explicit scope</strong><span>Boundaries and legal basis are recorded</span></div>
            <div className="platform-feature-card"><FileCheck size={16} /><strong>Evidence integrity</strong><span>Cryptographic chain of custody</span></div>
          </div>
        </div>
      ) : (
        <div className="platform-investigations-list">
          <div className="platform-investigations-toolbar">
            <div className="platform-search investigation-search"><Search size={14} /><input placeholder="Search investigations…" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} /></div>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} aria-label="Filter status"><option value="all">All statuses</option><option value="active">Active</option><option value="paused">Paused</option><option value="closed">Closed</option><option value="archived">Archived</option></select>
            <select value={priorityFilter} onChange={(event) => setPriorityFilter(event.target.value)} aria-label="Filter priority"><option value="all">All priorities</option><option value="critical">Critical</option><option value="high">High</option><option value="normal">Normal</option><option value="low">Low</option></select>
            <select value={sort} onChange={(event) => setSort(event.target.value as typeof sort)} aria-label="Sort investigations"><option value="updated">Recently updated</option><option value="name">Name</option><option value="priority">Priority</option></select>
            <span className="platform-investigations-count">{filteredCases.length} of {cases.length}</span>
          </div>

          <div className="platform-investigations-table-wrap">
            <table className="platform-table">
              <thead><tr><th>Investigation</th><th>Status</th><th>Priority</th><th>Entities</th><th>Relations / Evidence</th><th>Updated</th><th>Actions</th></tr></thead>
              <tbody>{filteredCases.map((item) => (
                <tr key={item.id} className={item.id === activeCase?.id ? "selected" : ""} onClick={() => onOpenCase(item.id)}>
                  <td><strong>{item.title}</strong><small>{item.summary || item.scope_statement}</small></td>
                  <td><span className={`platform-status ${item.status}`}>{item.status}</span></td>
                  <td><span className={`platform-status priority-${item.priority}`}>{item.priority}</span></td>
                  <td className="platform-numeric-cell">{item.entity_count}</td>
                  <td className="platform-numeric-cell">{item.relationship_count} / {item.source_count}</td>
                  <td><span className="platform-date"><Clock3 size={12} /> {formatDate(item.updated_at)}</span></td>
                  <td><div className="investigation-row-actions">
                    <button type="button" title="Open" aria-label={`Open ${item.title}`} onClick={(event) => { event.stopPropagation(); onOpenCase(item.id); }}><ArrowRight size={12} /></button>
                    <button type="button" title="Edit" aria-label={`Edit ${item.title}`} onClick={(event) => { event.stopPropagation(); setEditing(item); }}><Pencil size={12} /></button>
                    <button type="button" title="Duplicate" aria-label={`Duplicate ${item.title}`} onClick={(event) => { event.stopPropagation(); void onDuplicate(item.id); }}><Copy size={12} /></button>
                    <button type="button" title="Export" aria-label={`Export ${item.title}`} onClick={(event) => { event.stopPropagation(); void onExport(item.id, item.title); }}><Download size={12} /></button>
                    <button type="button" title={item.status === "archived" ? "Restore" : "Archive"} aria-label={`${item.status === "archived" ? "Restore" : "Archive"} ${item.title}`} onClick={(event) => { event.stopPropagation(); void onSetStatus(item.id, item.status === "archived" ? "active" : "archived"); }}>{item.status === "archived" ? <RotateCcw size={12} /> : <Archive size={12} />}</button>
                    <button type="button" className="danger" title="Delete" aria-label={`Delete ${item.title}`} onClick={(event) => { event.stopPropagation(); if (window.confirm(`Delete “${item.title}” and all of its local data? This cannot be undone.`)) void onDelete(item.id); }}><Trash2 size={12} /></button>
                  </div></td>
                </tr>
              ))}</tbody>
            </table>
          </div>

          {activeCase && <section className="platform-investigations-detail">
            <div className="platform-investigations-detail-header">
              <div><span className="platform-eyebrow">Active investigation</span><h2>{activeCase.title}</h2></div>
              <button type="button" className="platform-primary-btn" onClick={onOpenWorkspace}>Open graph <ArrowRight size={14} /></button>
              {canRerun && <button type="button" className="platform-secondary-btn" onClick={onRunAgain} disabled={loading}>{loading ? "Running…" : "Run discovery again"}</button>}
            </div>
            <div className="platform-investigations-detail-body">
              <div className="platform-investigations-detail-meta">
                <div className="platform-meta-item"><span className="platform-meta-label">Status</span><span className={`platform-status ${activeCase.status}`}>{activeCase.status}</span></div>
                <div className="platform-meta-item"><span className="platform-meta-label">Priority</span><span className="platform-meta-value">{activeCase.priority}</span></div>
                <div className="platform-meta-item"><span className="platform-meta-label">Legal basis</span><span className="platform-meta-value">{activeCase.legal_basis}</span></div>
                <div className="platform-meta-item"><span className="platform-meta-label">Entities</span><span className="platform-meta-value">{activeCase.entity_count}</span></div>
                <div className="platform-meta-item"><span className="platform-meta-label">Evidence</span><span className="platform-meta-value">{activeCase.source_count}</span></div>
                <div className="platform-meta-item"><span className="platform-meta-label">Custody</span><span className="platform-meta-value">{monitor ? (monitor.custody_intact ? "Verified" : "Review required") : "No sealed evidence"}</span></div>
              </div>
              <p className="platform-investigations-detail-summary">{activeCase.summary || activeCase.scope_statement}</p>
              {activeCase.tags.length > 0 && <div className="investigation-tags">{activeCase.tags.map((tag) => <span key={tag}>{tag}</span>)}</div>}
              {activeCase.notes && <div className="investigation-notes"><strong>Notes</strong><p>{activeCase.notes}</p></div>}
              <div className="investigation-linked-stats"><span>{activeCase.relationship_count} relationships</span><span>{activeCase.conversation_count} conversations</span><span>{activeCase.query_count} OSINT queries</span></div>
            </div>
          </section>}
        </div>
      )}

      <NewInvestigationDialog
        open={Boolean(editing)}
        loading={loading}
        initial={editing ? draftFromCase(editing) : undefined}
        title="Edit investigation"
        onClose={() => setEditing(null)}
        onSubmit={async (draft) => { if (editing) await onEdit(editing.id, draft); setEditing(null); }}
      />
    </div>
  );
}
