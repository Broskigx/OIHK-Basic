import { Layers3, ListTree, Plus } from "lucide-react";
import { FormEvent } from "react";
import type { ManualEntityForm } from "../types";

export function EntityDock({
  manualEntity,
  onManualEntityChange,
  onAddEntity,
  loading,
  activeCaseId,
  activeTargetId,
  onRunAgain,
  onPresetSource,
  onOpenIntake,
}: {
  manualEntity: ManualEntityForm;
  onManualEntityChange: (patch: Partial<ManualEntityForm>) => void;
  onAddEntity: (event: FormEvent) => void;
  loading: boolean;
  activeCaseId: string;
  activeTargetId: string;
  onRunAgain: () => void;
  onPresetSource: (mode: string, title: string) => void;
  onOpenIntake: () => void;
}) {
  return (
    <aside className="entity-dock">
      <div className="dock-title">
        <Layers3 size={16} />
        <span>Paleta</span>
      </div>
      <div className="palette-list">
        {[
          ["name", "Persona", "name-dot"],
          ["handle", "Alias", "alias-dot"],
          ["email", "Email", "email-dot"],
          ["url", "URL", "url-dot"],
          ["source", "Evidencia", "file-dot"],
        ].map(([type, label, dotClass]) => (
          <button
            key={type}
            className={manualEntity.type === type ? "selected" : ""}
            type="button"
            onClick={() => onManualEntityChange({ type })}
          >
            <span className={`entity-dot ${dotClass}`} />
            {label}
          </button>
        ))}
      </div>
      <form className="quick-entity-form" onSubmit={onAddEntity}>
        <label>
          <span>Nueva entidad</span>
          <input
            value={manualEntity.label}
            onChange={(event) => onManualEntityChange({ label: event.target.value })}
            placeholder="Alias, URL, email, evidencia..."
          />
        </label>
        <div className="mini-grid">
          <label>
            <span>Tipo</span>
            <select value={manualEntity.type} onChange={(event) => onManualEntityChange({ type: event.target.value })}>
              {["name", "handle", "email", "url", "phone", "organization", "source", "note"].map((type) => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Conf.</span>
            <input
              min="0"
              max="1"
              step="0.01"
              type="number"
              value={manualEntity.confidence}
              onChange={(event) => onManualEntityChange({ confidence: Number(event.target.value) })}
            />
          </label>
        </div>
        <button type="submit" disabled={loading || !activeCaseId || !manualEntity.label.trim()}>
          <Plus size={15} />
          Agregar al grafo
        </button>
      </form>
      <div className="dock-title compact-title">
        <ListTree size={16} />
        <span>Recolectores</span>
      </div>
      <div className="collector-list">
        <button type="button" onClick={onRunAgain} disabled={loading || !activeTargetId}>Indice publico</button>
        <button type="button" onClick={() => onPresetSource("url", "Public URL evidence")}>Web abierta</button>
        <button type="button" onClick={() => onPresetSource("text", "Analyst note")}>Notas del analista</button>
        <button type="button" onClick={onOpenIntake}>Archivos locales</button>
      </div>
    </aside>
  );
}
