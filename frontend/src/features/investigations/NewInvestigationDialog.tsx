import React from "react";

export function NewInvestigationDialog({
  open, intake, loading, onChange, onClose, onSubmit,
}: {
  open: boolean;
  intake: { first_name: string; last_name: string; aliases: string; notes: string; legal_basis: string; scope_statement: string; consent_basis: string; auto_search: boolean; photos: File[] };
  loading: boolean;
  onChange: (patch: Partial<typeof intake>) => void;
  onClose: () => void;
  onSubmit: (e: React.FormEvent) => void;
}) {
  if (!open) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>New Investigation</h2>
        <form onSubmit={onSubmit}>
          <div className="form-group">
            <label>First Name *</label>
            <input type="text" value={intake.first_name} onChange={(e) => onChange({ first_name: e.target.value })} required minLength={1} maxLength={120} />
          </div>
          <div className="form-group">
            <label>Last Name *</label>
            <input type="text" value={intake.last_name} onChange={(e) => onChange({ last_name: e.target.value })} required minLength={1} maxLength={120} />
          </div>
          <div className="form-group">
            <label>Aliases</label>
            <textarea value={intake.aliases} onChange={(e) => onChange({ aliases: e.target.value })} rows={2} placeholder="One per line or comma-separated" />
          </div>
          <div className="form-group">
            <label>Notes</label>
            <textarea value={intake.notes} onChange={(e) => onChange({ notes: e.target.value })} rows={3} />
          </div>
          <div className="form-group">
            <label>Legal Basis</label>
            <input type="text" value={intake.legal_basis} onChange={(e) => onChange({ legal_basis: e.target.value })} />
          </div>
          <div className="form-group">
            <label>Scope Statement</label>
            <textarea value={intake.scope_statement} onChange={(e) => onChange({ scope_statement: e.target.value })} rows={2} required minLength={12} />
          </div>
          <div className="form-group">
            <label>
              <input type="checkbox" checked={intake.auto_search} onChange={(e) => onChange({ auto_search: e.target.checked })} style={{ width: "auto", marginRight: "0.5rem" }} />
              Auto-run initial search
            </label>
          </div>
          <div className="modal-actions">
            <button type="button" onClick={onClose}>Cancel</button>
            <button type="submit" className="primary" disabled={loading}>
              {loading ? "Creating..." : "Create Investigation"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
