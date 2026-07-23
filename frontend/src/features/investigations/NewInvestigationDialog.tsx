import { ShieldCheck, X } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import type { InvestigationDraft } from "../../types";

const EMPTY_DRAFT: InvestigationDraft = {
  title: "",
  summary: "",
  legal_basis: "Authorized open-source research",
  scope_statement: "",
  priority: "normal",
  tags: [],
  notes: "",
};

export function NewInvestigationDialog({
  open,
  loading,
  initial,
  title = "New investigation",
  onClose,
  onSubmit,
}: {
  open: boolean;
  loading: boolean;
  initial?: InvestigationDraft;
  title?: string;
  onClose: () => void;
  onSubmit: (draft: InvestigationDraft) => Promise<void>;
}) {
  const [draft, setDraft] = useState<InvestigationDraft>(initial ?? EMPTY_DRAFT);
  const [tags, setTags] = useState((initial?.tags ?? []).join(", "));

  useEffect(() => {
    if (!open) return;
    setDraft(initial ?? EMPTY_DRAFT);
    setTags((initial?.tags ?? []).join(", "));
  }, [initial, open]);

  if (!open) return null;

  async function submit(event: FormEvent) {
    event.preventDefault();
    await onSubmit({
      ...draft,
      tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean).slice(0, 30),
    });
  }

  return (
    <div className="platform-dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="platform-dialog" role="dialog" aria-modal="true" aria-labelledby="investigation-dialog-title" onMouseDown={(event) => event.stopPropagation()}>
        <header>
          <div><span className="platform-eyebrow">Local investigation</span><h2 id="investigation-dialog-title">{title}</h2></div>
          <button type="button" className="platform-icon-button" onClick={onClose} aria-label="Close dialog"><X size={16} /></button>
        </header>
        <form onSubmit={(event) => void submit(event)}>
          <label>Investigation name
            <input value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} required minLength={3} maxLength={200} autoFocus />
          </label>
          <label>Description
            <textarea value={draft.summary} onChange={(event) => setDraft({ ...draft, summary: event.target.value })} rows={2} maxLength={20000} />
          </label>
          <div className="platform-form-grid two">
            <label>Legal basis
              <input value={draft.legal_basis} onChange={(event) => setDraft({ ...draft, legal_basis: event.target.value })} required minLength={3} maxLength={120} />
            </label>
            <label>Priority
              <select value={draft.priority} onChange={(event) => setDraft({ ...draft, priority: event.target.value as InvestigationDraft["priority"] })}>
                <option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option><option value="critical">Critical</option>
              </select>
            </label>
          </div>
          <label>Authorized scope
            <textarea value={draft.scope_statement} onChange={(event) => setDraft({ ...draft, scope_statement: event.target.value })} rows={3} required minLength={12} maxLength={20000} />
          </label>
          <label>Tags
            <input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="fraud, domain research, priority" />
          </label>
          <label>Investigation notes
            <textarea value={draft.notes} onChange={(event) => setDraft({ ...draft, notes: event.target.value })} rows={3} maxLength={50000} />
          </label>
          <footer>
            <span><ShieldCheck size={14} /> Scope and authorization are stored with the investigation.</span>
            <button type="submit" className="platform-primary" disabled={loading}>{loading ? "Saving…" : title.startsWith("Edit") ? "Save changes" : "Create investigation"}</button>
          </footer>
        </form>
      </section>
    </div>
  );
}
