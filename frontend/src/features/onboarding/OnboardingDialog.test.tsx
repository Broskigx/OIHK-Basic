import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ApplicationSettings } from "../../types";
import { OnboardingDialog } from "./OnboardingDialog";

const apiMocks = vi.hoisted(() => ({
  detect: vi.fn(),
  storage: vi.fn(),
  save: vi.fn(),
}));

vi.mock("../../api", () => ({
  detectLocalModelServices: apiMocks.detect,
  getStorageStatus: apiMocks.storage,
  saveLocalModelConfiguration: apiMocks.save,
}));

const settings: ApplicationSettings = {
  id: "settings",
  schema_version: 2,
  onboarding_complete: false,
  general: { language: "en", default_start: "dashboard", default_case_id: "", confirmations: true, check_updates: true, update_channel: "alpha" },
  appearance: { dark_mode: true, density: "comfortable", text_scale: 1, reduce_motion: false, restore_layout: true },
  storage: { data_directory: "", backup_on_exit: false, retention_days: 0 },
  tools: { executable_paths: {}, timeout_seconds: 120, max_file_mb: 250 },
  privacy: { telemetry_enabled: false, public_osint_enabled: true, redact_logs: true, log_retention_days: 14 },
  performance: { max_visible_nodes: 2500, worker_enabled: true, quality: "balanced", low_power_mode: false },
  updated_at: null,
};

afterEach(() => {
  vi.clearAllMocks();
  document.body.innerHTML = "";
});

describe("first-run local model discovery", () => {
  it("detects Ollama automatically and saves the selected connection", async () => {
    apiMocks.storage.mockResolvedValue({
      data_directory: "C:/OIHK-Basic",
      database_path: "C:/OIHK-Basic/oihk-basic.db",
      storage_path: "C:/OIHK-Basic/storage",
      database_bytes: 0,
      evidence_bytes: 0,
      total_bytes: 0,
      writable: true,
    });
    apiMocks.detect.mockResolvedValue({
      services: [{
        provider: "ollama",
        endpoint: "http://127.0.0.1:11434",
        status: "online",
        models: [{ id: "qwen-local", name: "qwen-local", context_length: 32768 }],
        latency_ms: 12,
        error: "",
      }],
    });
    apiMocks.save.mockImplementation(async (configuration) => ({ ...configuration, id: "saved" }));
    const onConnected = vi.fn();
    const host = document.createElement("div");
    document.body.append(host);
    const root = createRoot(host);

    await act(async () => {
      root.render(
        <OnboardingDialog
          open
          settings={settings}
          cases={[]}
          onComplete={vi.fn()}
          onCreateCase={vi.fn()}
          onLocalModelConnected={onConnected}
          onOpenModels={vi.fn()}
        />,
      );
    });

    expect(host.textContent).toContain("Ollama detected");
    const review = Array.from(host.querySelectorAll("button")).find((button) => button.textContent?.includes("Review & connect"));
    await act(async () => { review?.click(); });
    const connect = Array.from(host.querySelectorAll("button")).find((button) => button.textContent?.includes("Connect Ollama"));
    await act(async () => { connect?.click(); });

    expect(apiMocks.detect).toHaveBeenCalledOnce();
    expect(apiMocks.save).toHaveBeenCalledWith(expect.objectContaining({
      provider: "ollama",
      endpoint: "http://127.0.0.1:11434",
      model: "qwen-local",
      context_length: 32768,
    }));
    expect(onConnected).toHaveBeenCalledOnce();
    expect(host.textContent).toContain("Connected");

    await act(async () => { root.unmount(); });
  });
});
