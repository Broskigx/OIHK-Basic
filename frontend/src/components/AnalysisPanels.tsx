import { Activity, BrainCircuit, Camera, Database, FileText, LinkIcon, LockKeyhole, ServerCog, Upload } from "lucide-react";
import { ChangeEvent, FormEvent, useMemo } from "react";
import { safeExternalHref } from "../lib/safeUrl";
import type { AuditEvent, CaseMemory, ProviderCatalog, SearchHit, SourceForm, SourceRead, TargetPhoto } from "../types";
import { actionLabel, score, shortDate } from "../utils";

export function OutputConsole({
  hits,
  sources,
  memory,
}: {
  hits: SearchHit[];
  sources: SourceRead[];
  memory: CaseMemory[];
}) {
  return (
    <section className="output-console">
      <div className="console-header">
        <span>Salida de recoleccion</span>
        <small>{sources.length} fuentes / {memory.length} controles de verificacion</small>
      </div>
      <div className="console-lines">
        {(hits.length ? hits.slice(0, 5) : sources.slice(0, 5)).map((item) => (
          <div key={item.id} className="console-line">
            <span>{item.title}</span>
            <small>{"snippet" in item ? item.url : item.kind}</small>
          </div>
        ))}
        {hits.length === 0 && sources.length === 0 && <div className="empty-inline">Sin salida registrada</div>}
      </div>
    </section>
  );
}

export function IntelGrid({ hits, memory }: { hits: SearchHit[]; memory: CaseMemory[] }) {
  return (
    <section className="intel-grid subdued-grid">
      <div className="panel hits-panel">
        <div className="panel-title">
          <Activity size={18} />
          <span>Resultados recopilados</span>
        </div>
        <div className="hit-list">
          {hits.length === 0 && <div className="empty-inline">Sin resultados revisables</div>}
          {hits.map((hit) => (
            <a className="hit" key={hit.id} href={safeExternalHref(hit.url)} target="_blank" rel="noopener noreferrer">
              <strong>{hit.title}</strong>
              <span>{hit.snippet || hit.url}</span>
              <small>{score(hit.confidence)} confianza inicial</small>
            </a>
          ))}
        </div>
      </div>

      <div className="panel memory-panel">
        <div className="panel-title">
          <BrainCircuit size={18} />
          <span>Verificacion asistida</span>
        </div>
        <div className="memory-list">
          {memory.length === 0 && <div className="empty-inline">Sin notas de verificacion</div>}
          {memory.slice(0, 8).map((item) => (
            <article key={item.id} className="memory-item">
              <small>{item.kind} / {score(item.confidence)}</small>
              <span>{item.content}</span>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

export function EvidenceGrid({
  sourceForm,
  onSourceFormChange,
  onSubmitEvidence,
  loading,
  activeCaseId,
  photoUploading,
  targetPhotos,
  onAddPhotos,
  activeTargetId,
}: {
  sourceForm: SourceForm;
  onSourceFormChange: (patch: Partial<SourceForm>) => void;
  onSubmitEvidence: (event: FormEvent) => void;
  loading: boolean;
  activeCaseId: string;
  photoUploading: boolean;
  targetPhotos: TargetPhoto[];
  onAddPhotos: (event: ChangeEvent<HTMLInputElement>) => void;
  activeTargetId: string;
}) {
  return (
    <section className="evidence-grid">
      <form className="panel evidence-panel" onSubmit={onSubmitEvidence}>
        <div className="panel-title">
          <Upload size={18} />
          <span>Evidencia adicional</span>
        </div>
        <div className="segmented">
          <button type="button" className={sourceForm.mode === "text" ? "selected" : ""} onClick={() => onSourceFormChange({ mode: "text" })}>
            <FileText size={16} />
            Texto
          </button>
          <button type="button" className={sourceForm.mode === "url" ? "selected" : ""} onClick={() => onSourceFormChange({ mode: "url" })}>
            <LinkIcon size={16} />
            URL
          </button>
        </div>
        <input value={sourceForm.title} onChange={(event) => onSourceFormChange({ title: event.target.value })} />
        {sourceForm.mode === "url" ? (
          <input value={sourceForm.url} onChange={(event) => onSourceFormChange({ url: event.target.value })} placeholder="https://example.org/page" />
        ) : (
          <textarea value={sourceForm.body} onChange={(event) => onSourceFormChange({ body: event.target.value })} rows={6} />
        )}
        <button type="submit" disabled={loading || !activeCaseId}>
          <Upload size={16} />
          Guardar
        </button>
      </form>
      <div className="panel person-photos-panel">
        <div className="panel-title">
          <Camera size={18} />
          <span>Fotos de la persona</span>
        </div>
        <label className="photo-drop photo-drop-small">
          <Camera size={17} />
          <span>{photoUploading ? "Adjuntando..." : "Adjuntar fotos al expediente"}</span>
          <input type="file" accept="image/*" multiple onChange={onAddPhotos} disabled={photoUploading || !activeTargetId} />
        </label>
        <div className="person-photo-list">
          {targetPhotos.length === 0 && <div className="empty-inline">Sin fotos asociadas al objetivo</div>}
          {targetPhotos.map((photo) => (
            <article key={photo.id} className="person-photo-card">
              <div>
                <strong>{photo.filename}</strong>
                <span>{photo.content_type} / {(photo.size_bytes / 1024).toFixed(1)} KB</span>
              </div>
              <code>{photo.sha256.slice(0, 24)}...</code>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

export function SourceBand({ sources }: { sources: SourceRead[] }) {
  return (
    <section className="source-band">
      {sources.slice(0, 8).map((source) => (
        <article key={source.id} className="source-card">
          <strong>{source.title}</strong>
          <span>{source.kind}</span>
          <small>{score(source.reliability)} fiabilidad</small>
        </article>
      ))}
    </section>
  );
}

export function EnterpriseGrid({
  providerCatalog,
  auditEvents,
}: {
  providerCatalog: ProviderCatalog | null;
  auditEvents: AuditEvent[];
}) {
  const providerCategories = useMemo(
    () => Object.entries(providerCatalog?.categories ?? {}).sort((a, b) => b[1] - a[1]).slice(0, 6),
    [providerCatalog],
  );
  const configuredProviders = useMemo(
    () => providerCatalog?.providers.filter((provider) => provider.configured).slice(0, 8) ?? [],
    [providerCatalog],
  );

  return (
    <section className="enterprise-grid">
      <div className="panel provider-panel">
        <div className="panel-title">
          <Database size={18} />
          <span>Proveedores de datos</span>
        </div>
        <div className="provider-stats">
          <div>
            <strong>{providerCatalog?.total ?? 0}</strong>
            <span>catalogados</span>
          </div>
          <div>
            <strong>{providerCatalog?.operational ?? 0}</strong>
            <span>operacionales</span>
          </div>
          <div>
            <strong>{providerCatalog?.catalogued ?? 0}</strong>
            <span>sin verificar</span>
          </div>
        </div>
        <div className="provider-categories">
          {providerCategories.map(([category, count]) => (
            <span key={category}>
              {category.replace(/_/g, " ")}
              <b>{count}</b>
            </span>
          ))}
        </div>
        <div className="provider-list">
          {configuredProviders.map((provider) => (
            <div key={provider.id}>
              <ServerCog size={14} />
              <span>{provider.name}</span>
              <small>{provider.status}</small>
            </div>
          ))}
          {configuredProviders.length === 0 && <div className="empty-inline">Sin proveedores configurados aun</div>}
        </div>
      </div>

      <div className="panel audit-panel">
        <div className="panel-title">
          <LockKeyhole size={18} />
          <span>Auditoria empresarial</span>
        </div>
        <div className="audit-list">
          {auditEvents.slice(0, 10).map((event) => (
            <article key={event.id}>
              <strong>{actionLabel(event.action)}</strong>
              <span>{event.actor} / {shortDate(event.created_at)}</span>
              <code>{JSON.stringify(event.payload).slice(0, 180)}</code>
            </article>
          ))}
          {auditEvents.length === 0 && <div className="empty-inline">Sin eventos auditables</div>}
        </div>
      </div>
    </section>
  );
}
