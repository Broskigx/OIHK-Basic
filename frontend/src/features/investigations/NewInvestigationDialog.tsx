import { CheckCircle2, ShieldCheck, X, ArrowLeft, ArrowRight, FolderLock, Search, Target } from "lucide-react";
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

const STEPS = [
  { label: "Basics", icon: <FolderLock size={16} /> },
  { label: "Scope", icon: <Target size={16} /> },
  { label: "Initial Entity", icon: <Search size={16} /> },
  { label: "Review", icon: <CheckCircle2 size={16} /> },
];

export function NewInvestigationDialog({
  open,
  loading,
  initial,
  title = "New Investigation",
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
  const [step, setStep] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!open) return;
    setDraft(initial ?? EMPTY_DRAFT);
    setTags((initial?.tags ?? []).join(", "));
    setStep(0);
    setErrors({});
  }, [initial, open]);

  if (!open) return null;

  const validateStep = (): boolean => {
    const newErrors: Record<string, string> = {};
    if (step === 0) {
      if (!draft.title.trim() || draft.title.trim().length < 3) newErrors.title = "Title must be at least 3 characters";
      if (!draft.summary.trim()) newErrors.summary = "Description is required";
    }
    if (step === 1) {
      if (!draft.scope_statement.trim() || draft.scope_statement.trim().length < 12) newErrors.scope = "Scope must be at least 12 characters";
      if (!draft.legal_basis.trim()) newErrors.legal = "Legal basis is required";
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const nextStep = () => {
    if (validateStep()) setStep((s) => Math.min(STEPS.length - 1, s + 1));
  };

  const prevStep = () => {
    setStep((s) => Math.max(0, s - 1));
    setErrors({});
  };

  async function submit(event: FormEvent) {
    event.preventDefault();
    await onSubmit({
      ...draft,
      tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean).slice(0, 30),
    });
  }

  return (
    <div className="platform-dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="platform-dialog platform-dialog-wide" role="dialog" aria-modal="true" aria-labelledby="investigation-dialog-title" onMouseDown={(event) => event.stopPropagation()}>
        {/* Header */}
        <header className="platform-dialog-header">
          <div className="platform-dialog-header-info">
            <span className="platform-dialog-icon"><FolderLock size={20} /></span>
            <div>
              <h2 id="investigation-dialog-title">{title}</h2>
              <p className="platform-dialog-subtitle">Create an authorized local investigation workspace.</p>
            </div>
          </div>
          <button type="button" className="platform-icon-button" onClick={onClose} aria-label="Close dialog">
            <X size={16} />
          </button>
        </header>

        {/* Step indicator */}
        <div className="platform-dialog-steps">
          {STEPS.map((s, i) => (
            <div key={s.label} className={`platform-dialog-step ${i === step ? "active" : i < step ? "complete" : ""}`}>
              <span className="platform-dialog-step-icon">
                {i < step ? <CheckCircle2 size={14} /> : s.icon}
              </span>
              <span className="platform-dialog-step-label">{s.label}</span>
              {i < STEPS.length - 1 && <div className="platform-dialog-step-line" />}
            </div>
          ))}
        </div>

        {/* Content */}
        <div className="platform-dialog-content">
          {step === 0 && (
            <div className="platform-dialog-step-panel">
              <label>
                Investigation name
                <span className="platform-field-hint">A descriptive title for this investigation</span>
                <input
                  value={draft.title}
                  onChange={(event) => setDraft({ ...draft, title: event.target.value })}
                  required minLength={3} maxLength={200} autoFocus
                  placeholder="e.g., GAMBLER-2026-0803"
                />
                {errors.title && <span className="platform-field-error">{errors.title}</span>}
              </label>
              <label>
                Description
                <span className="platform-field-hint">Brief summary of the investigation purpose</span>
                <textarea
                  value={draft.summary}
                  onChange={(event) => setDraft({ ...draft, summary: event.target.value })}
                  rows={3} maxLength={20000}
                  placeholder="Authorized research into..."
                />
                {errors.summary && <span className="platform-field-error">{errors.summary}</span>}
              </label>
              <label>
                Priority
                <span className="platform-field-hint">Operational priority level</span>
                <select value={draft.priority} onChange={(event) => setDraft({ ...draft, priority: event.target.value as InvestigationDraft["priority"] })}>
                  <option value="low">Low</option>
                  <option value="normal">Normal</option>
                  <option value="high">High</option>
                  <option value="critical">Critical</option>
                </select>
              </label>
            </div>
          )}

          {step === 1 && (
            <div className="platform-dialog-step-panel">
              <label>
                Authorized scope
                <span className="platform-field-hint">Define permitted targets, sources, and boundaries</span>
                <textarea
                  value={draft.scope_statement}
                  onChange={(event) => setDraft({ ...draft, scope_statement: event.target.value })}
                  rows={4} required minLength={12} maxLength={20000}
                  placeholder="This investigation is authorized to examine..."
                />
                {errors.scope && <span className="platform-field-error">{errors.scope}</span>}
              </label>
              <label>
                Legal basis
                <span className="platform-field-hint">Legal or regulatory authority for this investigation</span>
                <input
                  value={draft.legal_basis}
                  onChange={(event) => setDraft({ ...draft, legal_basis: event.target.value })}
                  required minLength={3} maxLength={120}
                  placeholder="Authorized open-source research"
                />
                {errors.legal && <span className="platform-field-error">{errors.legal}</span>}
              </label>
              <label>
                Tags
                <span className="platform-field-hint">Comma-separated keywords for organization</span>
                <input
                  value={tags}
                  onChange={(event) => setTags(event.target.value)}
                  placeholder="fraud, domain research, priority"
                />
              </label>
            </div>
          )}

          {step === 2 && (
            <div className="platform-dialog-step-panel">
              <label>
                Initial entity (optional)
                <span className="platform-field-hint">Add the first entity to investigate</span>
                <input
                  value={draft.notes}
                  onChange={(event) => setDraft({ ...draft, notes: event.target.value })}
                  placeholder="Domain, email, or identifier"
                />
              </label>
              <p className="platform-field-note">You can add entities later from the Intelligence Graph or Entities workspace.</p>
            </div>
          )}

          {step === 3 && (
            <div className="platform-dialog-step-panel">
              <div className="platform-dialog-review">
                <div className="platform-dialog-review-item">
                  <span>Title</span>
                  <strong>{draft.title || "—"}</strong>
                </div>
                <div className="platform-dialog-review-item">
                  <span>Description</span>
                  <p>{draft.summary || "—"}</p>
                </div>
                <div className="platform-dialog-review-item">
                  <span>Scope</span>
                  <p>{draft.scope_statement || "—"}</p>
                </div>
                <div className="platform-dialog-review-item">
                  <span>Legal basis</span>
                  <strong>{draft.legal_basis}</strong>
                </div>
                <div className="platform-dialog-review-item">
                  <span>Priority</span>
                  <strong>{draft.priority}</strong>
                </div>
                {tags && (
                  <div className="platform-dialog-review-item">
                    <span>Tags</span>
                    <div className="platform-dialog-review-tags">
                      {tags.split(",").filter(Boolean).map((t) => (
                        <span key={t.trim()} className="placo-tag">{t.trim()}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <footer className="platform-dialog-footer">
          <div className="platform-dialog-footer-left">
            <ShieldCheck size={14} />
            <span>Scope and authorization are stored with the investigation.</span>
          </div>
          <div className="platform-dialog-footer-actions">
            <button type="button" className="platform-ghost-btn" onClick={onClose}>
              Cancel
            </button>
            {step > 0 && (
              <button type="button" className="platform-ghost-btn" onClick={prevStep}>
                <ArrowLeft size={14} /> Back
              </button>
            )}
            {step < STEPS.length - 1 ? (
              <button type="button" className="platform-primary-btn" onClick={nextStep}>
                Continue <ArrowRight size={14} />
              </button>
            ) : (
              <button type="button" className="platform-primary-btn" onClick={(event) => void submit(event as unknown as FormEvent)} disabled={loading}>
                {loading ? "Creating..." : "Create Investigation"}
              </button>
            )}
          </div>
        </footer>
      </section>
    </div>
  );
}