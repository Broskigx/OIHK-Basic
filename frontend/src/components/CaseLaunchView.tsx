import { Activity, BrainCircuit, Camera, Fingerprint, Layers3, ListTree, Network, Search, ShieldCheck } from "lucide-react";
import { FormEvent, useState } from "react";
import type { GraphRead, IntakeForm, ProviderCatalog } from "../types";
import { GraphView } from "./GraphView";

export function CaseLaunchView({
  intake,
  onIntakeChange,
  loading,
  providerCatalog,
  preparedGraph,
  onSubmit,
}: {
  intake: IntakeForm;
  onIntakeChange: (patch: Partial<IntakeForm>) => void;
  loading: boolean;
  providerCatalog: ProviderCatalog | null;
  preparedGraph: GraphRead;
  onSubmit: (event: FormEvent) => void;
}) {
  const [launchTab, setLaunchTab] = useState("Nuevo expediente");
  const [caseKind, setCaseKind] = useState("Persona / POI");

  return (
    <section className="case-launch">
      <div className="launch-ribbon">
        <div className="ribbon-tabs">
          {["Nuevo expediente", "Plantillas", "Fuentes", "Auditoria"].map((tab) => (
            <button
              key={tab}
              className={launchTab === tab ? "ribbon-tab active" : "ribbon-tab"}
              type="button"
              onClick={() => setLaunchTab(tab)}
            >
              {tab}
            </button>
          ))}
        </div>
        <div className="ribbon-tools">
          <button type="button" onClick={() => setLaunchTab("Auditoria")}>
            <ShieldCheck size={15} />
            Guardrails
          </button>
          <button type="button" onClick={() => onIntakeChange({ auto_search: !intake.auto_search })}>
            <BrainCircuit size={15} />
            {intake.auto_search ? "IA activa" : "IA pausada"}
          </button>
          <button type="button" onClick={() => setLaunchTab("Fuentes")}>
            <Network size={15} />
            Grafo preparado
          </button>
        </div>
      </div>

      <div className="launch-grid">
        <aside className="launch-panel launch-left">
          <div className="dock-title">
            <Layers3 size={16} />
            <span>Tipo de investigacion</span>
          </div>
          <div className="launch-selector">
            {["Persona / POI", "Alias / Handle", "Organizacion", "Infraestructura"].map((kind) => (
              <button
                key={kind}
                className={caseKind === kind ? "selected" : ""}
                type="button"
                onClick={() => setCaseKind(kind)}
              >
                {kind}
              </button>
            ))}
          </div>

          <div className="dock-title compact-title">
            <ListTree size={16} />
            <span>Fuentes habilitadas</span>
          </div>
          <div className="source-checklist">
            <label><input checked readOnly type="checkbox" /> {providerCatalog?.total ?? 0} conectores catalogados</label>
            <label><input checked readOnly type="checkbox" /> {providerCatalog?.operational ?? 0} operacionales / {providerCatalog?.configured ?? 0} configurados</label>
            <label><input checked readOnly type="checkbox" /> Fuentes internas y externas</label>
            <label><input checked readOnly type="checkbox" /> Credenciales visibles por estado</label>
          </div>
        </aside>

        <form className="intake-panel launch-form" onSubmit={onSubmit}>
          <div className="launch-form-header">
            <div>
              <span className="section-kicker">OIHK intake</span>
              <h2>Preparacion de expediente</h2>
            </div>
            <span className="case-badge">Case seed</span>
          </div>

          <div className="form-section">
            <div className="section-label">
              <span>01</span>
              <strong>Identidad semilla</strong>
            </div>
            <div className="identity-grid">
              <label>
                <span>Nombre</span>
                <input value={intake.first_name} onChange={(event) => onIntakeChange({ first_name: event.target.value })} required />
              </label>
              <label>
                <span>Apellido</span>
                <input value={intake.last_name} onChange={(event) => onIntakeChange({ last_name: event.target.value })} required />
              </label>
            </div>
            <label>
              <span>Aliases, handles o variantes</span>
              <input value={intake.aliases} onChange={(event) => onIntakeChange({ aliases: event.target.value })} />
            </label>
          </div>

          <div className="form-section">
            <div className="section-label">
              <span>02</span>
              <strong>Evidencia inicial</strong>
            </div>
            <label>
              <span>Notas del analista</span>
              <textarea value={intake.notes} onChange={(event) => onIntakeChange({ notes: event.target.value })} rows={4} />
            </label>
            <label className="photo-drop compact-drop">
              <Camera size={19} />
              <span>{intake.photos.length ? `${intake.photos.length} foto(s) listas para hashing` : "Adjuntar fotos como evidencia local"}</span>
              <input
                type="file"
                accept="image/*"
                multiple
                onChange={(event) => onIntakeChange({ photos: Array.from(event.target.files ?? []) })}
              />
            </label>
          </div>

          <div className="form-section">
            <div className="section-label">
              <span>03</span>
              <strong>Autorizacion y alcance</strong>
            </div>
            <div className="identity-grid">
              <label>
                <span>Base legal</span>
                <input value={intake.legal_basis} onChange={(event) => onIntakeChange({ legal_basis: event.target.value })} required />
              </label>
              <label>
                <span>Autorizacion</span>
                <input value={intake.consent_basis} onChange={(event) => onIntakeChange({ consent_basis: event.target.value })} required />
              </label>
            </div>
            <label>
              <span>Alcance operativo</span>
              <textarea value={intake.scope_statement} onChange={(event) => onIntakeChange({ scope_statement: event.target.value })} rows={3} required />
            </label>
          </div>

          <div className="launch-submit-row">
            <label className="toggle">
              <input
                type="checkbox"
                checked={intake.auto_search}
                onChange={(event) => onIntakeChange({ auto_search: event.target.checked })}
              />
              <span>Ejecutar busqueda IA al crear expediente</span>
            </label>
            <button className="primary" type="submit" disabled={loading}>
              <Search size={17} />
              Crear expediente y abrir grafo
            </button>
          </div>
        </form>

        <aside className="launch-panel launch-right">
          <div className="dock-title">
            <Fingerprint size={16} />
            <span>Estado operativo</span>
          </div>
          <div className="readiness-list">
            <div><strong>Vault local</strong><span>Fotos con SHA-256</span></div>
            <div><strong>Procedencia</strong><span>Fuentes y citas obligatorias</span></div>
            <div><strong>Planner IA</strong><span>NVIDIA si hay clave, fallback local</span></div>
            <div><strong>Proveedores</strong><span>{providerCatalog?.total ?? 0} conectores declarados</span></div>
            <div><strong>Grafo</strong><span>Entidad semilla creada al iniciar</span></div>
          </div>

          <div className="dock-title compact-title">
            <Activity size={16} />
            <span>Vista previa de ejecucion</span>
          </div>
          <div className="run-preview">
            <div><span>1</span> Crear caso y objetivo</div>
            <div><span>2</span> Hashear evidencia local</div>
            <div><span>3</span> Generar queries controladas</div>
            <div><span>4</span> Abrir canvas de grafo</div>
          </div>

          <div className="dock-title compact-title">
            <Network size={16} />
            <span>Previsualizacion de grafo</span>
          </div>
          <div className="launch-graph-preview">
            <GraphView graph={preparedGraph} compact />
          </div>
        </aside>
      </div>
    </section>
  );
}
