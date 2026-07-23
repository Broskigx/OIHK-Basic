import { ArrowLeft, ArrowRight, Bot, CheckCircle2, Database, FolderLock, Rocket, Search, ShieldCheck, Wrench, X } from "lucide-react";
import { useEffect, useState } from "react";
import { detectLocalModelServices, getStorageStatus } from "../../api";
import type { ApplicationSettings, CaseRead, InvestigationDraft, LocalModelServiceProbe, StorageStatus } from "../../types";

const STEPS = ["Welcome", "Privacy", "Storage", "Local models", "Model setup", "Tools", "First investigation", "Ready"];

export function OnboardingDialog({
  open,
  settings,
  cases,
  onComplete,
  onCreateCase,
  onOpenModels,
}: {
  open: boolean;
  settings: ApplicationSettings | null;
  cases: CaseRead[];
  onComplete: () => Promise<void>;
  onCreateCase: (draft: InvestigationDraft) => Promise<CaseRead>;
  onOpenModels: () => void;
}) {
  const [step, setStep] = useState(0);
  const [storage, setStorage] = useState<StorageStatus | null>(null);
  const [services, setServices] = useState<LocalModelServiceProbe[]>([]);
  const [detecting, setDetecting] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createdCase, setCreatedCase] = useState<CaseRead | null>(null);
  const [name, setName] = useState("");
  const [scope, setScope] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setStep(0);
    setError("");
    getStorageStatus().then(setStorage).catch(() => setStorage(null));
  }, [open]);

  if (!open || !settings) return null;

  async function detect() {
    setDetecting(true);
    setError("");
    try {
      const result = await detectLocalModelServices();
      setServices(result.services);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not detect local model services");
    } finally {
      setDetecting(false);
    }
  }

  async function createFirstCase() {
    if (name.trim().length < 3 || scope.trim().length < 12) {
      setError("Enter a name and an authorized scope of at least 12 characters.");
      return;
    }
    setCreating(true);
    setError("");
    try {
      const result = await onCreateCase({
        title: name.trim(),
        summary: "Created during OIHK Basic onboarding.",
        legal_basis: "Authorized open-source research",
        scope_statement: scope.trim(),
        priority: "normal",
        tags: [],
        notes: "",
      });
      setCreatedCase(result);
      setStep(7);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create the investigation");
    } finally {
      setCreating(false);
    }
  }

  async function finish() {
    await onComplete();
  }

  return (
    <div className="onboarding-backdrop" role="presentation">
      <section className="onboarding-dialog" role="dialog" aria-modal="true" aria-labelledby="onboarding-title">
        <aside>
          <div className="onboarding-brand"><ShieldCheck size={21} /><strong>OIHK Basic</strong></div>
          <ol>{STEPS.map((label, index) => <li key={label} className={index === step ? "active" : index < step ? "complete" : ""}><span>{index < step ? <CheckCircle2 size={13} /> : index + 1}</span>{label}</li>)}</ol>
        </aside>
        <main>
          <button type="button" className="onboarding-skip" onClick={() => void finish()}><X size={14} /> Skip setup</button>

          {step === 0 && <div className="onboarding-step"><Rocket size={34} /><span>Welcome</span><h1 id="onboarding-title">Your private investigation workspace</h1><p>OIHK Basic combines local case management, an interactive graph, evidence tools, public-source lookups, reports, and optional local AI.</p></div>}
          {step === 1 && <div className="onboarding-step"><FolderLock size={34} /><span>Local privacy</span><h1>Data stays under your control</h1><p>Cases, graph records, OSINT history, and Copilot conversations are stored by the local service. Public connections occur only when you run an explicit lookup. Telemetry is off by default.</p><div className="onboarding-note"><ShieldCheck size={15} /> Copilot requires a model endpoint you select. OIHK Basic never silently falls back to a cloud model.</div></div>}
          {step === 2 && <div className="onboarding-step"><Database size={34} /><span>Storage</span><h1>Use the recommended application directory</h1><p>OIHK Basic selects the correct per-user application-data directory for Windows, macOS, or Linux. This avoids developer-specific paths and preserves data during upgrades.</p><dl><div><dt>Data directory</dt><dd>{storage?.data_directory ?? "Checking local storage…"}</dd></div><div><dt>Status</dt><dd>{storage?.writable ? "Writable and ready" : "Waiting for local service"}</dd></div></dl></div>}
          {step === 3 && <div className="onboarding-step"><Search size={34} /><span>Detection</span><h1>Find LM Studio or Ollama</h1><p>This check probes only common loopback endpoints. No model is downloaded and no cloud account is required.</p><button type="button" onClick={() => void detect()} disabled={detecting}><Search size={14} /> {detecting ? "Detecting…" : "Detect local services"}</button>{services.length > 0 && <div className="onboarding-services">{services.map((service) => <div key={`${service.provider}-${service.endpoint}`}><strong>{service.provider}</strong><span>{service.status} · {service.models.length} models · {service.latency_ms} ms</span></div>)}</div>}</div>}
          {step === 4 && <div className="onboarding-step"><Bot size={34} /><span>Optional</span><h1>Configure a local model when you are ready</h1><p>Copilot is optional. Every investigation, graph, evidence, OSINT, and reporting feature remains available without a model.</p><button type="button" onClick={onOpenModels}><Bot size={14} /> Open Local Models</button><small>You can return to onboarding from Settings.</small></div>}
          {step === 5 && <div className="onboarding-step"><Wrench size={34} /><span>Health checks</span><h1>Core tools are ready</h1><div className="onboarding-checks"><div><CheckCircle2 size={15} /><span><strong>Local API</strong> Connected</span></div><div><CheckCircle2 size={15} /><span><strong>SQLite</strong> {storage?.writable ? "Writable" : "Status pending"}</span></div><div><CheckCircle2 size={15} /><span><strong>Graph renderer</strong> Available</span></div><div><CheckCircle2 size={15} /><span><strong>Local models</strong> Optional</span></div></div></div>}
          {step === 6 && <div className="onboarding-step"><Database size={34} /><span>First investigation</span><h1>Create your first workspace</h1>{cases.length > 0 ? <div className="onboarding-note"><CheckCircle2 size={15} /> You already have {cases.length} investigation{cases.length === 1 ? "" : "s"}. You can continue without creating another.</div> : <><label>Investigation name<input value={name} onChange={(event) => setName(event.target.value)} placeholder="Authorized research case" /></label><label>Authorized scope<textarea rows={3} value={scope} onChange={(event) => setScope(event.target.value)} placeholder="Define permitted targets, sources, and boundaries" /></label><button type="button" onClick={() => void createFirstCase()} disabled={creating}>{creating ? "Creating…" : "Create investigation"}</button></>}</div>}
          {step === 7 && <div className="onboarding-step"><CheckCircle2 size={34} /><span>Ready</span><h1>OIHK Basic is ready</h1><p>{createdCase ? `“${createdCase.title}” is stored locally and ready to open.` : "Open the dashboard to continue with your local investigations."}</p><button type="button" className="onboarding-finish" onClick={() => void finish()}><Rocket size={14} /> Open dashboard</button></div>}

          {error && <div className="platform-inline-error">{error}</div>}
          <footer><button type="button" onClick={() => setStep((current) => Math.max(0, current - 1))} disabled={step === 0}><ArrowLeft size={14} /> Back</button><span>{step + 1} / {STEPS.length}</span>{step < 7 && <button type="button" className="onboarding-next" onClick={() => setStep((current) => Math.min(7, current + 1))}>{step === 6 ? "Skip for now" : "Continue"} <ArrowRight size={14} /></button>}</footer>
        </main>
      </section>
    </div>
  );
}
