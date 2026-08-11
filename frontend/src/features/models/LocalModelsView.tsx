import {
  CheckCircle2,
  Download,
  Gauge,
  Loader2,
  RefreshCw,
  Save,
  ServerCog,
  ShieldCheck,
  Upload,
  WifiOff,
  Zap,
} from "lucide-react";
import { ChangeEvent, useEffect, useRef, useState } from "react";
import {
  detectLocalModelServices,
  getLocalModelConfiguration,
  listLocalModels,
  saveLocalModelConfiguration,
  testLocalModel,
} from "../../api";
import type {
  LocalModelConfiguration,
  LocalModelDescriptor,
  LocalModelProviderId,
  LocalModelServiceProbe,
} from "../../types";
import { WorkspaceHeader } from "../../shared/ui/WorkspaceHeader";

const EMPTY_CONFIGURATION: LocalModelConfiguration = {
  provider: "ollama",
  endpoint: "",
  model: "",
  context_length: 8192,
  temperature: 0.2,
  max_tokens: 900,
  timeout_seconds: 150,
  streaming: true,
  system_prompt: "",
  capabilities: ["chat"],
  tools_enabled: [],
  role_models: {},
  fallback_model: "",
};

const PROVIDERS: { id: LocalModelProviderId; label: string; detail: string }[] = [
  { id: "lmstudio", label: "LM Studio", detail: "OpenAI-compatible local server" },
  { id: "ollama", label: "Ollama", detail: "Native Ollama local API" },
  { id: "openai_compatible", label: "Compatible", detail: "Private OpenAI-compatible endpoint" },
];

const MODEL_ROLES = ["chat", "extraction", "summary", "classification", "reasoning"];

function formatBytes(value?: number | null): string {
  if (!value) return "Size not reported";
  return `${(value / 1024 / 1024 / 1024).toFixed(1)} GB`;
}

export function LocalModelsView({ onStatusChanged }: { onStatusChanged?: () => void }) {
  const [configuration, setConfiguration] = useState<LocalModelConfiguration>(EMPTY_CONFIGURATION);
  const [models, setModels] = useState<LocalModelDescriptor[]>([]);
  const [services, setServices] = useState<LocalModelServiceProbe[]>([]);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const importRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getLocalModelConfiguration()
      .then((saved) => {
        if (saved) setConfiguration(saved);
      })
      .catch((cause) => setError(cause instanceof Error ? cause.message : "Could not load local model settings"))
      .finally(() => setLoading(false));
  }, []);

  function patch(patchValue: Partial<LocalModelConfiguration>) {
    setConfiguration((current) => ({ ...current, ...patchValue }));
    setMessage("");
  }

  async function detect() {
    setLoading(true);
    setError("");
    try {
      const result = await detectLocalModelServices();
      setServices(result.services);
      const online = result.services.find((service) => service.status === "online");
      if (online && !configuration.endpoint) {
        patch({
          provider: online.provider,
          endpoint: online.endpoint,
          model: online.models[0]?.id ?? "",
        });
        setModels(online.models);
      }
      setMessage(online ? `Detected ${online.provider} in ${online.latency_ms} ms` : "No local model service responded");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Detection failed");
    } finally {
      setLoading(false);
    }
  }

  async function refreshModels() {
    if (!configuration.endpoint.trim()) {
      setError("Enter or detect a local endpoint first.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const result = await listLocalModels(configuration.provider, configuration.endpoint);
      setModels(result.models);
      if (!result.models.some((model) => model.id === configuration.model)) {
        patch({ model: result.models[0]?.id ?? "" });
      }
      setMessage(`${result.models.length} local model${result.models.length === 1 ? "" : "s"} available`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not list models");
    } finally {
      setLoading(false);
    }
  }

  async function save() {
    if (!configuration.endpoint.trim()) {
      setError("A private local endpoint is required.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const saved = await saveLocalModelConfiguration(configuration);
      setConfiguration(saved);
      setMessage("Local model configuration saved");
      onStatusChanged?.();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not save configuration");
    } finally {
      setLoading(false);
    }
  }

  async function test() {
    if (!configuration.endpoint || !configuration.model) {
      setError("Choose an endpoint and model before testing inference.");
      return;
    }
    setTesting(true);
    setError("");
    try {
      const result = await testLocalModel({
        provider: configuration.provider,
        endpoint: configuration.endpoint,
        model: configuration.model,
        prompt: "Respond with: OIHK local model ready",
        temperature: configuration.temperature,
        max_tokens: Math.min(configuration.max_tokens, 80),
        timeout_seconds: configuration.timeout_seconds,
      });
      setMessage(`Inference succeeded in ${result.latency_ms} ms · ${result.reply.slice(0, 120)}`);
      onStatusChanged?.();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Inference test failed");
    } finally {
      setTesting(false);
    }
  }

  function exportConfiguration() {
    const safe = { ...configuration, id: undefined, updated_at: undefined };
    const url = URL.createObjectURL(new Blob([JSON.stringify(safe, null, 2)], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "oihk-local-model.json";
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function importConfiguration(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    file.text()
      .then((text) => {
        const parsed = JSON.parse(text) as Partial<LocalModelConfiguration>;
        if (!PROVIDERS.some((provider) => provider.id === parsed.provider) || typeof parsed.endpoint !== "string") {
          throw new Error("Invalid OIHK local model configuration");
        }
        patch({ ...EMPTY_CONFIGURATION, ...parsed, id: undefined, updated_at: undefined });
        setMessage("Configuration imported. Review and save it to activate.");
      })
      .catch((cause) => setError(cause instanceof Error ? cause.message : "Could not import configuration"));
  }

  return (
    <div className="platform-view local-models-view">
      <WorkspaceHeader
        eyebrow="Local inference"
        title="Local Models"
        description="Connect OIHK to models running on this computer or private infrastructure you control. Prompts and evidence stay within that boundary."
        actions={
          <>
            <button type="button" onClick={() => void detect()} disabled={loading}>
              {loading ? <Loader2 size={14} className="ip-spin" /> : <RefreshCw size={14} />} Detect services
            </button>
            <button type="button" className="platform-primary" onClick={() => void save()} disabled={loading}>
              <Save size={14} /> Save configuration
            </button>
          </>
        }
      />

      <div className="local-privacy-note"><ShieldCheck size={16} /> No cloud provider is required or enabled by this page.</div>
      {error && <div className="platform-inline-error" role="alert">{error}</div>}
      {message && <div className="platform-inline-success" role="status">{message}</div>}

      <div className="local-provider-grid" aria-label="Local model providers">
        {PROVIDERS.map((provider) => {
          const detected = services.find((service) => service.provider === provider.id);
          return (
            <button
              type="button"
              key={provider.id}
              className={configuration.provider === provider.id ? "local-provider-card active" : "local-provider-card"}
              onClick={() => patch({ provider: provider.id })}
            >
              <ServerCog size={18} />
              <span><strong>{provider.label}</strong><small>{provider.detail}</small></span>
              {detected && (
                <i className={detected.status === "online" ? "online" : "offline"}>
                  {detected.status === "online" ? <CheckCircle2 size={13} /> : <WifiOff size={13} />}{detected.status}
                </i>
              )}
            </button>
          );
        })}
      </div>

      <div className="local-model-layout">
        <section className="platform-section local-model-config">
          <div className="platform-section-heading"><div><span className="platform-eyebrow">Connection</span><h2>Inference endpoint</h2></div></div>
          <label>Private endpoint<input value={configuration.endpoint} onChange={(event) => patch({ endpoint: event.target.value })} placeholder="http://127.0.0.1:port" /></label>
          <div className="local-inline-field">
            <label>Active model
              <select value={configuration.model} onChange={(event) => patch({ model: event.target.value })}>
                <option value="">Select a detected model</option>
                {models.map((model) => <option key={model.id} value={model.id}>{model.name}</option>)}
              </select>
            </label>
            <button type="button" onClick={() => void refreshModels()} disabled={loading}><RefreshCw size={14} /> List models</button>
          </div>
          <div className="local-settings-grid">
            <label>Context length<input type="number" min={256} value={configuration.context_length} onChange={(event) => patch({ context_length: Number(event.target.value) })} /></label>
            <label>Max output tokens<input type="number" min={1} value={configuration.max_tokens} onChange={(event) => patch({ max_tokens: Number(event.target.value) })} /></label>
            <label>Temperature<input type="number" min={0} max={2} step={0.1} value={configuration.temperature} onChange={(event) => patch({ temperature: Number(event.target.value) })} /></label>
            <label>Timeout (seconds)<input type="number" min={2} max={600} value={configuration.timeout_seconds} onChange={(event) => patch({ timeout_seconds: Number(event.target.value) })} /></label>
          </div>
          <label>System prompt<textarea rows={4} value={configuration.system_prompt} onChange={(event) => patch({ system_prompt: event.target.value })} placeholder="Optional local policy or analyst instructions" /></label>
          <label className="local-checkbox"><input type="checkbox" checked={configuration.streaming} onChange={(event) => patch({ streaming: event.target.checked })} /> Stream model output when supported</label>
          <div className="local-config-actions">
            <button type="button" onClick={() => void test()} disabled={testing || loading}>{testing ? <Loader2 size={14} className="ip-spin" /> : <Zap size={14} />} Test inference</button>
            <button type="button" onClick={exportConfiguration}><Download size={14} /> Export</button>
            <button type="button" onClick={() => importRef.current?.click()}><Upload size={14} /> Import</button>
            <input ref={importRef} type="file" accept="application/json,.json" hidden onChange={importConfiguration} />
          </div>
        </section>

        <aside className="platform-section local-models-catalog">
          <div className="platform-section-heading"><div><span className="platform-eyebrow">Catalog</span><h2>{models.length ? `${models.length} available` : "No models listed"}</h2></div><Gauge size={18} /></div>
          {models.length === 0 ? <p className="platform-muted">Detect a service or list models from the configured endpoint.</p> : models.map((model) => (
            <button type="button" key={model.id} className={configuration.model === model.id ? "active" : ""} onClick={() => patch({ model: model.id })}>
              <span><strong>{model.name}</strong><small>{formatBytes(model.size_bytes)}{model.context_length ? ` · ${model.context_length.toLocaleString()} context` : ""}</small></span>
              {configuration.model === model.id && <CheckCircle2 size={15} />}
            </button>
          ))}
          <div className="local-role-models">
            <span className="platform-eyebrow">Task routing</span>
            {MODEL_ROLES.map((role) => (
              <label key={role}>{role}
                <select value={configuration.role_models[role] ?? ""} onChange={(event) => patch({ role_models: { ...configuration.role_models, [role]: event.target.value } })}>
                  <option value="">Use active model</option>
                  {models.map((model) => <option key={model.id} value={model.id}>{model.name}</option>)}
                </select>
              </label>
            ))}
            <label>fallback
              <select value={configuration.fallback_model} onChange={(event) => patch({ fallback_model: event.target.value })}>
                <option value="">Deterministic local fallback</option>
                {models.map((model) => <option key={model.id} value={model.id}>{model.name}</option>)}
              </select>
            </label>
          </div>
        </aside>
      </div>
    </div>
  );
}
