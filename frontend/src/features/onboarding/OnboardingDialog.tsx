import {
  ArrowLeft,
  ArrowRight,
  Bot,
  CheckCircle2,
  Database,
  FolderLock,
  Loader2,
  PlugZap,
  Radar,
  RefreshCw,
  Rocket,
  ServerOff,
  ShieldCheck,
  Wrench,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import {
  detectLocalModelServices,
  getStorageStatus,
  saveLocalModelConfiguration,
} from "../../api";
import type {
  ApplicationSettings,
  CaseRead,
  InvestigationDraft,
  LocalModelProviderId,
  LocalModelServiceProbe,
  StorageStatus,
} from "../../types";
import {
  configurationFromProbe,
  localModelProviderLabel,
} from "../models/localModelConfiguration";

const STEPS = ["Welcome", "Privacy", "Storage", "Local models", "Model setup", "Tools", "First investigation", "Ready"];

type DiscoveryState = "scanning" | "complete" | "failed";

export function OnboardingDialog({
  open,
  settings,
  cases,
  onComplete,
  onCreateCase,
  onLocalModelConnected,
  onOpenModels,
}: {
  open: boolean;
  settings: ApplicationSettings | null;
  cases: CaseRead[];
  onComplete: () => Promise<void>;
  onCreateCase: (draft: InvestigationDraft) => Promise<CaseRead>;
  onLocalModelConnected: () => void;
  onOpenModels: () => void;
}) {
  const [step, setStep] = useState(0);
  const [storage, setStorage] = useState<StorageStatus | null>(null);
  const [services, setServices] = useState<LocalModelServiceProbe[]>([]);
  const [discoveryState, setDiscoveryState] = useState<DiscoveryState>("scanning");
  const [selectedModels, setSelectedModels] = useState<Record<string, string>>({});
  const [connectingProvider, setConnectingProvider] = useState<LocalModelProviderId | null>(null);
  const [connectedProvider, setConnectedProvider] = useState<LocalModelProviderId | null>(null);
  const [creating, setCreating] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const [createdCase, setCreatedCase] = useState<CaseRead | null>(null);
  const [name, setName] = useState("");
  const [scope, setScope] = useState("");
  const [error, setError] = useState("");

  const onlineServices = services.filter((service) => service.status === "online");

  useEffect(() => {
    if (!open) return;
    let cancelled = false;

    setStep(0);
    setError("");
    setServices([]);
    setSelectedModels({});
    setConnectedProvider(null);
    setConnectingProvider(null);
    setDiscoveryState("scanning");

    getStorageStatus()
      .then((result) => { if (!cancelled) setStorage(result); })
      .catch(() => { if (!cancelled) setStorage(null); });

    detectLocalModelServices()
      .then((result) => {
        if (cancelled) return;
        setServices(result.services);
        setSelectedModels(Object.fromEntries(
          result.services.map((service) => [service.provider, service.models[0]?.id ?? ""]),
        ));
        setDiscoveryState("complete");
      })
      .catch((cause) => {
        if (cancelled) return;
        setDiscoveryState("failed");
        setError(cause instanceof Error ? cause.message : "Could not detect local model services");
      });

    return () => { cancelled = true; };
  }, [open]);

  if (!open || !settings) return null;

  async function detect() {
    setDiscoveryState("scanning");
    setError("");
    try {
      const result = await detectLocalModelServices();
      setServices(result.services);
      setSelectedModels(Object.fromEntries(
        result.services.map((service) => [service.provider, service.models[0]?.id ?? ""]),
      ));
      setDiscoveryState("complete");
    } catch (cause) {
      setDiscoveryState("failed");
      setError(cause instanceof Error ? cause.message : "Could not detect local model services");
    }
  }

  async function connect(service: LocalModelServiceProbe) {
    setConnectingProvider(service.provider);
    setError("");
    try {
      await saveLocalModelConfiguration(configurationFromProbe(service, selectedModels[service.provider]));
      setConnectedProvider(service.provider);
      onLocalModelConnected();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : `Could not connect ${localModelProviderLabel(service.provider)}`);
    } finally {
      setConnectingProvider(null);
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
    setFinishing(true);
    setError("");
    try {
      await onComplete();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not finish first-run setup");
      setFinishing(false);
    }
  }

  const discoverySummary = onlineServices.map((service) => localModelProviderLabel(service.provider)).join(" + ");

  return (
    <div className="onboarding-backdrop" role="presentation">
      <section className="onboarding-dialog" role="dialog" aria-modal="true" aria-labelledby="onboarding-heading">
        <aside>
          <div className="onboarding-brand"><ShieldCheck size={21} /><strong>OIHK Basic</strong></div>
          <ol>{STEPS.map((label, index) => <li key={label} className={index === step ? "active" : index < step ? "complete" : ""}><span>{index < step ? <CheckCircle2 size={13} /> : index + 1}</span>{label}</li>)}</ol>
          <small>Local-first desktop setup</small>
        </aside>
        <main>
          <button type="button" className="onboarding-skip" onClick={() => void finish()} disabled={finishing || Boolean(connectingProvider)}><X size={14} /> Skip setup</button>

          {step === 0 && (
            <div className="onboarding-step onboarding-welcome">
              <Rocket size={34} />
              <span>Welcome</span>
              <h1 id="onboarding-heading">Your private investigation workspace</h1>
              <p>OIHK Basic combines local case management, an interactive graph, evidence tools, public-source lookups, reports, and optional local AI.</p>
              <div className={`onboarding-discovery ${discoveryState}${onlineServices.length > 0 ? " detected" : ""}`} aria-live="polite">
                <div className="onboarding-discovery-icon">
                  {discoveryState === "scanning" ? <Radar size={22} /> : onlineServices.length > 0 ? <CheckCircle2 size={22} /> : <ServerOff size={22} />}
                </div>
                <div>
                  <strong>{discoveryState === "scanning" ? "Scanning this computer…" : onlineServices.length > 0 ? `${discoverySummary} detected` : "No local AI runtime detected"}</strong>
                  <small>{discoveryState === "scanning" ? "Checking LM Studio and Ollama on loopback only." : onlineServices.length > 0 ? "A local runtime is ready. Would you like to connect it?" : "You can retry or configure a private endpoint manually."}</small>
                </div>
                {discoveryState !== "scanning" && onlineServices.length > 0 && <button type="button" onClick={() => setStep(3)}>Review & connect <ArrowRight size={14} /></button>}
              </div>
            </div>
          )}
          {step === 1 && <div className="onboarding-step"><FolderLock size={34} /><span>Local privacy</span><h1 id="onboarding-heading">Data stays under your control</h1><p>Cases, graph records, OSINT history, and Copilot conversations are stored by the local service. Public connections occur only when you run an explicit lookup. Telemetry is off by default.</p><div className="onboarding-note"><ShieldCheck size={15} /> Copilot requires a model endpoint you select. OIHK Basic never silently falls back to a cloud model.</div></div>}
          {step === 2 && <div className="onboarding-step"><Database size={34} /><span>Storage</span><h1 id="onboarding-heading">Use the recommended application directory</h1><p>OIHK Basic selects the correct per-user application-data directory for Windows, macOS, or Linux. This avoids developer-specific paths and preserves data during upgrades.</p><dl><div><dt>Data directory</dt><dd>{storage?.data_directory ?? "Checking local storage…"}</dd></div><div><dt>Status</dt><dd>{storage?.writable ? "Writable and ready" : "Waiting for local service"}</dd></div></dl></div>}
          {step === 3 && (
            <div className="onboarding-step onboarding-model-discovery">
              <Radar size={34} className={discoveryState === "scanning" ? "onboarding-radar" : ""} />
              <span>Automatic detection</span>
              <h1 id="onboarding-heading">Connect LM Studio or Ollama</h1>
              <p>OIHK probes only private loopback endpoints. Choose a detected runtime below, or keep using OIHK Basic without AI.</p>
              {discoveryState === "scanning" ? (
                <div className="onboarding-scanning" role="status"><Loader2 size={20} /> <span><strong>Looking for local runtimes</strong><small>LM Studio · 127.0.0.1:1234<br />Ollama · 127.0.0.1:11434</small></span></div>
              ) : onlineServices.length > 0 ? (
                <div className="onboarding-services">
                  {onlineServices.map((service) => {
                    const label = localModelProviderLabel(service.provider);
                    const connected = connectedProvider === service.provider;
                    return (
                      <article key={`${service.provider}-${service.endpoint}`} className={connected ? "connected" : ""}>
                        <div className="onboarding-service-mark"><Bot size={19} /></div>
                        <div className="onboarding-service-copy">
                          <div><strong>{label} detected</strong><span><i /> Online · {service.latency_ms} ms</span></div>
                          <small>{service.endpoint} · {service.models.length} model{service.models.length === 1 ? "" : "s"}</small>
                          {service.models.length > 0 && <label>Model<select value={selectedModels[service.provider] ?? ""} onChange={(event) => setSelectedModels((current) => ({ ...current, [service.provider]: event.target.value }))}>{service.models.map((model) => <option key={model.id} value={model.id}>{model.name}</option>)}</select></label>}
                        </div>
                        <button type="button" className={connected ? "onboarding-connected" : "onboarding-connect"} onClick={() => void connect(service)} disabled={Boolean(connectingProvider) || connected}>
                          {connectingProvider === service.provider ? <><Loader2 size={14} /> Connecting…</> : connected ? <><CheckCircle2 size={14} /> Connected</> : <><PlugZap size={14} /> Connect {label}</>}
                        </button>
                      </article>
                    );
                  })}
                </div>
              ) : (
                <div className="onboarding-no-services"><ServerOff size={22} /><div><strong>No runtime responded</strong><small>Start the local server in LM Studio or Ollama, then scan again.</small></div></div>
              )}
              <div className="onboarding-model-actions">
                <button type="button" onClick={() => void detect()} disabled={discoveryState === "scanning"}><RefreshCw size={14} /> Scan again</button>
                <button type="button" onClick={onOpenModels}><Wrench size={14} /> Configure manually</button>
              </div>
              <small className="onboarding-local-only"><ShieldCheck size={13} /> No model is downloaded. No cloud account or API key is used.</small>
            </div>
          )}
          {step === 4 && <div className="onboarding-step"><Bot size={34} /><span>Optional</span><h1 id="onboarding-heading">{connectedProvider ? `${localModelProviderLabel(connectedProvider)} is connected` : "Configure a local model when you are ready"}</h1><p>{connectedProvider ? "The selected endpoint and model are saved locally. You can fine-tune context, task routing, and inference settings at any time." : "Copilot is optional. Every investigation, graph, evidence, OSINT, and reporting feature remains available without a model."}</p>{connectedProvider && <div className="onboarding-note"><CheckCircle2 size={15} /> Local AI connection saved successfully.</div>}<button type="button" onClick={onOpenModels}><Bot size={14} /> Open manual configuration</button><small>You can return to onboarding from Settings.</small></div>}
          {step === 5 && <div className="onboarding-step"><Wrench size={34} /><span>Health checks</span><h1 id="onboarding-heading">Core tools are ready</h1><div className="onboarding-checks"><div><CheckCircle2 size={15} /><span><strong>Local API</strong> Connected</span></div><div><CheckCircle2 size={15} /><span><strong>SQLite</strong> {storage?.writable ? "Writable" : "Status pending"}</span></div><div><CheckCircle2 size={15} /><span><strong>Graph renderer</strong> Available</span></div><div><CheckCircle2 size={15} /><span><strong>Local models</strong> {connectedProvider ? `${localModelProviderLabel(connectedProvider)} connected` : "Optional"}</span></div></div></div>}
          {step === 6 && <div className="onboarding-step"><Database size={34} /><span>First investigation</span><h1 id="onboarding-heading">Create your first workspace</h1>{cases.length > 0 ? <div className="onboarding-note"><CheckCircle2 size={15} /> You already have {cases.length} investigation{cases.length === 1 ? "" : "s"}. You can continue without creating another.</div> : <><label>Investigation name<input value={name} onChange={(event) => setName(event.target.value)} placeholder="Authorized research case" /></label><label>Authorized scope<textarea rows={3} value={scope} onChange={(event) => setScope(event.target.value)} placeholder="Define permitted targets, sources, and boundaries" /></label><button type="button" onClick={() => void createFirstCase()} disabled={creating}>{creating ? "Creating…" : "Create investigation"}</button></>}</div>}
          {step === 7 && <div className="onboarding-step"><CheckCircle2 size={34} /><span>Ready</span><h1 id="onboarding-heading">OIHK Basic is ready</h1><p>{createdCase ? `“${createdCase.title}” is stored locally and ready to open.` : "Open the dashboard to continue with your local investigations."}</p><button type="button" className="onboarding-finish" onClick={() => void finish()} disabled={finishing}>{finishing ? <><Loader2 size={14} /> Finishing…</> : <><Rocket size={14} /> Open dashboard</>}</button></div>}

          {error && <div className="platform-inline-error" role="alert">{error}</div>}
          <footer><button type="button" onClick={() => setStep((current) => Math.max(0, current - 1))} disabled={step === 0}><ArrowLeft size={14} /> Back</button><span>{step + 1} / {STEPS.length}</span>{step < 7 && <button type="button" className="onboarding-next" onClick={() => setStep((current) => Math.min(7, current + 1))}>{step === 6 ? "Skip for now" : "Continue"} <ArrowRight size={14} /></button>}</footer>
        </main>
      </section>
    </div>
  );
}
