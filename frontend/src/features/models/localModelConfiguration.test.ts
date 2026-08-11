import { describe, expect, it } from "vitest";
import type { LocalModelServiceProbe } from "../../types";
import {
  configurationFromProbe,
  localModelProviderLabel,
} from "./localModelConfiguration";

const probe: LocalModelServiceProbe = {
  provider: "ollama",
  endpoint: "http://127.0.0.1:11434",
  status: "online",
  models: [
    { id: "qwen-local", name: "qwen-local", context_length: 32768 },
    { id: "small-local", name: "small-local" },
  ],
  latency_ms: 18,
  error: "",
};

describe("local model onboarding configuration", () => {
  it("builds a safe complete configuration from a detected runtime", () => {
    expect(configurationFromProbe(probe)).toMatchObject({
      provider: "ollama",
      endpoint: "http://127.0.0.1:11434",
      model: "qwen-local",
      context_length: 32768,
      streaming: true,
      capabilities: ["chat"],
    });
  });

  it("uses the requested model and a bounded default context when metadata is absent", () => {
    const result = configurationFromProbe(probe, "small-local");
    expect(result.model).toBe("small-local");
    expect(result.context_length).toBe(8192);
  });

  it("formats first-party provider names for the discovery UI", () => {
    expect(localModelProviderLabel("lmstudio")).toBe("LM Studio");
    expect(localModelProviderLabel("ollama")).toBe("Ollama");
  });
});
