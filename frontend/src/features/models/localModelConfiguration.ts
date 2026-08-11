import type {
  LocalModelConfiguration,
  LocalModelProviderId,
  LocalModelServiceProbe,
} from "../../types";

export const DEFAULT_LOCAL_MODEL_CONFIGURATION: LocalModelConfiguration = {
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

export function localModelProviderLabel(provider: LocalModelProviderId): string {
  if (provider === "lmstudio") return "LM Studio";
  if (provider === "ollama") return "Ollama";
  return "OpenAI-compatible endpoint";
}

export function configurationFromProbe(
  service: LocalModelServiceProbe,
  modelId = service.models[0]?.id ?? "",
): LocalModelConfiguration {
  const model = service.models.find((candidate) => candidate.id === modelId);
  return {
    ...DEFAULT_LOCAL_MODEL_CONFIGURATION,
    provider: service.provider,
    endpoint: service.endpoint,
    model: modelId,
    context_length: model?.context_length ?? DEFAULT_LOCAL_MODEL_CONFIGURATION.context_length,
  };
}
