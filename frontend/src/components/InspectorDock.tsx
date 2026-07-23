import {
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  FileText,
  Fingerprint,
  Gauge,
  LinkIcon,
  Maximize2,
  Move,
  Network,
  Play,
  Plus,
  Save,
  Tags,
  Trash2,
} from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { createGraphEntity, getEntityDossier, renameEntity, updateEntityDetails } from "../api";
import { ForensicsPanel } from "../ForensicsPanel";
import type {
  CaseMonitor,
  CaseRead,
  CustodyReport,
  EntityDossier,
  GraphNode,
  SearchRun,
  TargetProfile,
} from "../types";
import { score, shortDate } from "../utils";

const RELATION_PRESETS: { value: string; label: string }[] = [
  { value: "pareja", label: "Pareja" },
  { value: "familiar", label: "Familiar" },
  { value: "padre_madre", label: "Padre / Madre" },
  { value: "hijo_a", label: "Hijo / Hija" },
  { value: "hermano_a", label: "Hermano / Hermana" },
  { value: "amigo_a", label: "Amigo / Amiga" },
  { value: "colega", label: "Colega / Trabajo" },
  { value: "conocido_a", label: "Conocido / Conocida" },
];

export function InspectorDock({
  hitsCount,
  nodeCount,
  edgeCount,
  monitor,
  custody,
  activeCase,
  activeTarget,
  latestRun,
  caseId,
  activeTargetId,
  loading,
  expanding,
  pivotInfo,
  openedNode,
  onRunAgain,
  onExpandNode,
  onConnectHere,
  onOpenNode,
  onNodeRenamed,
  onDataChanged,
  onError,
  showForensics,
}: {
  hitsCount: number;
  nodeCount: number;
  edgeCount: number;
  monitor: CaseMonitor | null;
  custody: CustodyReport | null;
  activeCase?: CaseRead;
  activeTarget?: TargetProfile;
  latestRun?: SearchRun;
  caseId: string;
  activeTargetId: string;
  loading: boolean;
  expanding: boolean;
  pivotInfo: string;
  openedNode: GraphNode | null;
  onRunAgain: () => void;
  onExpandNode: (node: GraphNode) => void;
  onConnectHere: (node: GraphNode) => void;
  onOpenNode: (node: GraphNode) => void;
  onNodeRenamed: (node: GraphNode) => void;
  onDataChanged: () => Promise<void>;
  onError: (message: string) => void;
  showForensics: boolean;
}) {
  const [dossier, setDossier] = useState<EntityDossier | null>(null);
  const [dossierLoading, setDossierLoading] = useState(false);
  const [renameValue, setRenameValue] = useState("");
  const [relationForm, setRelationForm] = useState({ relation: RELATION_PRESETS[0].value, name: "" });
  const [relationBusy, setRelationBusy] = useState(false);
  const [props, setProps] = useState<{ key: string; value: string }[]>([]);
  const [notesValue, setNotesValue] = useState("");
  const [detailsBusy, setDetailsBusy] = useState(false);

  // Load the full dossier (sources + connections) whenever a real node is opened.
  useEffect(() => {
    setRenameValue(openedNode?.label ?? "");
    setProps(Object.entries(openedNode?.properties ?? {}).map(([key, value]) => ({ key, value: String(value) })));
    setNotesValue(openedNode?.notes ?? "");
    if (!openedNode || openedNode.id.startsWith("prepared-")) {
      setDossier(null);
      return;
    }
    let cancelled = false;
    setDossierLoading(true);
    getEntityDossier(openedNode.id)
      .then((data) => {
        if (!cancelled) setDossier(data);
      })
      .catch(() => {
        if (!cancelled) setDossier(null);
      })
      .finally(() => {
        if (!cancelled) setDossierLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [openedNode]);

  async function submitRename(event: FormEvent) {
    event.preventDefault();
    if (!openedNode || openedNode.id.startsWith("prepared-")) return;
    const label = renameValue.trim();
    if (!label || label === openedNode.label) return;
    onError("");
    try {
      const updated = await renameEntity(openedNode.id, label);
      onNodeRenamed(updated);
      if (caseId) await onDataChanged();
    } catch (err) {
      onError(err instanceof Error ? err.message : "No se pudo renombrar el nodo");
    }
  }

  async function submitDetails() {
    if (!openedNode || openedNode.id.startsWith("prepared-")) return;
    setDetailsBusy(true);
    onError("");
    try {
      const properties: Record<string, string> = {};
      for (const { key, value } of props) {
        const k = key.trim();
        if (k && value.trim()) properties[k] = value;
      }
      const updated = await updateEntityDetails(openedNode.id, { properties, notes: notesValue });
      onNodeRenamed(updated);
      if (caseId) await onDataChanged();
    } catch (err) {
      onError(err instanceof Error ? err.message : "No se pudieron guardar las propiedades");
    } finally {
      setDetailsBusy(false);
    }
  }

  async function addRelation(event: FormEvent) {
    event.preventDefault();
    if (!caseId || !openedNode || openedNode.id.startsWith("prepared-")) return;
    const name = relationForm.name.trim();
    if (!name) return;
    setRelationBusy(true);
    onError("");
    try {
      await createGraphEntity({
        case_id: caseId,
        label: name,
        type: "name",
        confidence: 0.7,
        connect_to_id: openedNode.id,
        relation_label: relationForm.relation,
      });
      setRelationForm({ ...relationForm, name: "" });
      await onDataChanged();
      const fresh = await getEntityDossier(openedNode.id);
      setDossier(fresh);
    } catch (err) {
      onError(err instanceof Error ? err.message : "No se pudo agregar el vínculo");
    } finally {
      setRelationBusy(false);
    }
  }

  return (
    <aside className="inspector-dock">
      <div className="status-strip compact-stats">
        <div>
          <span>{hitsCount}</span>
          <small>Resultados</small>
        </div>
        <div>
          <span>{nodeCount}</span>
          <small>Entidades</small>
        </div>
        <div>
          <span>{edgeCount}</span>
          <small>Enlaces</small>
        </div>
        <div>
          <span>{monitor?.sealed_count ?? custody?.sealed_count ?? 0}</span>
          <small>Sellos</small>
        </div>
      </div>

      <div className="inspector-card ops-live">
        <div className="dock-title">
          <Gauge size={16} />
          <span>Monitor en vivo</span>
        </div>
        <div className="ops-live-grid">
          <div>
            <span>Estado</span>
            <strong>{monitor?.status ?? activeCase?.status ?? "pendiente"}</strong>
          </div>
          <div>
            <span>Actividad</span>
            <strong>{shortDate(monitor?.latest_activity_at)}</strong>
          </div>
          <div>
            <span>Recolectores</span>
            <strong>{monitor?.active_search_runs ?? 0} activos</strong>
          </div>
          <div>
            <span>Custodia</span>
            <strong>{monitor?.custody_intact === false ? "alterada" : "integra"}</strong>
          </div>
        </div>
        <div className="risk-flags">
          {(monitor?.risk_flags.length ? monitor.risk_flags : ["sin_flags"]).map((flag) => (
            <span key={flag} className={flag === "sin_flags" ? "ok" : "warn"}>
              {flag === "sin_flags" ? <CheckCircle2 size={13} /> : <AlertTriangle size={13} />}
              {flag.replace(/_/g, " ")}
            </span>
          ))}
        </div>
      </div>

      <div className="search-card inspector-card">
        <div className="panel-title">
        <BrainCircuit size={19} />
        <span>Motor IA</span>
        </div>
        <div className="run-line">
          <strong>{latestRun?.provider ?? "sin corrida"}</strong>
          <span>{latestRun ? `${latestRun.status} / ${latestRun.hit_count} hits` : "pendiente"}</span>
        </div>
        <div className="query-list">
          {(latestRun?.queries ?? []).slice(0, 4).map((query) => (
            <code key={query}>{query}</code>
          ))}
        </div>
        <button onClick={onRunAgain} disabled={loading || !activeTargetId}>
          <Play size={16} />
          Relanzar
        </button>
      </div>

      <div className="inspector-card target-card">
        <div className="dock-title">
          <Fingerprint size={16} />
          <span>Inspector</span>
        </div>
        <strong>{openedNode?.label ?? (activeTarget ? `${activeTarget.first_name} ${activeTarget.last_name}` : "Sin objetivo")}</strong>
        <small>{openedNode ? `${openedNode.type} / ${score(openedNode.confidence)} confianza` : activeCase?.scope_statement ?? "Caso sin alcance activo"}</small>
        {openedNode && (
          <div className="node-inspector">
            {openedNode.id.startsWith("prepared-") ? (
              <p className="hint-inline">Vista previa — lanza la investigación para editar y expandir este nodo.</p>
            ) : (
              <form className="rename-row" onSubmit={submitRename}>
                <input
                  value={renameValue}
                  onChange={(event) => setRenameValue(event.target.value)}
                  placeholder="Nombre del nodo"
                  aria-label="Renombrar nodo"
                />
                <button
                  type="submit"
                  disabled={!renameValue.trim() || renameValue.trim() === openedNode.label}
                >
                  <CheckCircle2 size={14} />
                  Guardar
                </button>
              </form>
            )}

            <div className="ni-meta">
              <span>{openedNode.type}</span>
              <span>{score(openedNode.confidence)}</span>
              <span>{(dossier?.sources.length ?? openedNode.source_ids.length)} fuentes</span>
              <span>{dossier?.connections.length ?? 0} vínculos</span>
            </div>

            {!openedNode.id.startsWith("prepared-") && (
              <div className="ni-section ni-props">
                <div className="dock-subtitle">
                  <Tags size={13} />
                  Propiedades
                </div>
                {props.map((row, index) => (
                  <div key={index} className="ni-prop-row">
                    <input
                      value={row.key}
                      placeholder="clave"
                      aria-label="clave"
                      onChange={(event) =>
                        setProps((current) => current.map((r, i) => (i === index ? { ...r, key: event.target.value } : r)))
                      }
                    />
                    <input
                      value={row.value}
                      placeholder="valor"
                      aria-label="valor"
                      onChange={(event) =>
                        setProps((current) => current.map((r, i) => (i === index ? { ...r, value: event.target.value } : r)))
                      }
                    />
                    <button
                      type="button"
                      aria-label="Quitar propiedad"
                      onClick={() => setProps((current) => current.filter((_, i) => i !== index))}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))}
                <button
                  type="button"
                  className="ni-prop-add"
                  onClick={() => setProps((current) => [...current, { key: "", value: "" }])}
                >
                  <Plus size={13} /> Añadir propiedad
                </button>
                <textarea
                  className="ni-notes"
                  value={notesValue}
                  onChange={(event) => setNotesValue(event.target.value)}
                  placeholder="Notas del analista sobre este nodo…"
                  rows={2}
                />
                <button type="button" className="ni-details-save" onClick={submitDetails} disabled={detailsBusy}>
                  <Save size={13} /> {detailsBusy ? "Guardando…" : "Guardar propiedades y notas"}
                </button>
              </div>
            )}

            <div className="ni-actions">
              {openedNode.type === "url" && openedNode.label.startsWith("http") && (
                <a className="button" href={openedNode.label} target="_blank" rel="noreferrer">
                  <Maximize2 size={14} />
                  Abrir URL
                </a>
              )}
              <button type="button" onClick={() => onConnectHere(openedNode)}>
                <Move size={14} />
                Conectar aquí
              </button>
              {!openedNode.id.startsWith("prepared-") && (
                <button
                  type="button"
                  className="expand-node"
                  onClick={() => onExpandNode(openedNode)}
                  disabled={expanding}
                >
                  <Network size={14} />
                  {expanding ? "Expandiendo…" : "Expandir"}
                </button>
              )}
            </div>
            {pivotInfo && <p className="pivot-info">{pivotInfo}</p>}

            {!openedNode.id.startsWith("prepared-") && (
              <form className="relation-form" onSubmit={addRelation}>
                <div className="dock-subtitle">
                  <Plus size={13} />
                  Añadir familiar / amigo / pareja
                </div>
                <select
                  value={relationForm.relation}
                  onChange={(event) => setRelationForm({ ...relationForm, relation: event.target.value })}
                >
                  {RELATION_PRESETS.map((preset) => (
                    <option key={preset.value} value={preset.value}>
                      {preset.label}
                    </option>
                  ))}
                </select>
                <div className="relation-row">
                  <input
                    value={relationForm.name}
                    onChange={(event) => setRelationForm({ ...relationForm, name: event.target.value })}
                    placeholder="Nombre de la persona"
                  />
                  <button type="submit" disabled={relationBusy || !relationForm.name.trim()}>
                    {relationBusy ? "…" : "Vincular"}
                  </button>
                </div>
              </form>
            )}

            {dossierLoading && <p className="hint-inline">Cargando expediente…</p>}

            {dossier && dossier.connections.length > 0 && (
              <div className="ni-section">
                <div className="dock-subtitle">
                  <LinkIcon size={13} />
                  Vínculos ({dossier.connections.length})
                </div>
                <div className="ni-connections">
                  {dossier.connections.map((connection) => (
                    <button
                      key={connection.relationship_id}
                      type="button"
                      className="ni-conn"
                      onClick={() => onOpenNode(connection.entity)}
                    >
                      <span className="ni-conn-top">
                        <span className="ni-conn-rel">{connection.relation.replace(/_/g, " ")}</span>
                        <span
                          className={`ni-conn-conf${
                            connection.confidence >= 0.75 ? " high" : connection.confidence >= 0.5 ? " mid" : " low"
                          }`}
                          title="Confiabilidad del vínculo"
                        >
                          {score(connection.confidence)}
                        </span>
                      </span>
                      <span className="ni-conn-name">{connection.entity.label}</span>
                      <span className="ni-conn-type">{connection.entity.type}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {dossier && dossier.sources.length > 0 && (
              <div className="ni-section">
                <div className="dock-subtitle">
                  <FileText size={13} />
                  Fuentes ({dossier.sources.length})
                </div>
                <div className="ni-sources">
                  {dossier.sources.map((source) => (
                    <div key={source.source_id} className="ni-source">
                      {source.url ? (
                        <a href={source.url} target="_blank" rel="noreferrer">
                          {source.title}
                        </a>
                      ) : (
                        <strong>{source.title}</strong>
                      )}
                      <small>
                        {source.kind} · {score(source.reliability)}
                      </small>
                      {source.excerpt && <p>{source.excerpt}</p>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {dossier &&
              !dossierLoading &&
              dossier.sources.length === 0 &&
              dossier.connections.length === 0 && (
                <p className="hint-inline">Sin información recolectada todavía para este nodo.</p>
              )}
          </div>
        )}
      </div>
      {showForensics && caseId && (
        <ForensicsPanel caseId={caseId} onAnalyzed={() => void onDataChanged()} />
      )}
    </aside>
  );
}
