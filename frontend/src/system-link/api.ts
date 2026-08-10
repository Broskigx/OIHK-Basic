import { request } from "../api";
import type {
  LifecycleResult,
  LinkedSystemModule,
  ModuleLifecycleAction,
  PairingStart,
  PendingPairing,
  SystemLinkStatus,
} from "./types";

export function getSystemLinkStatus(): Promise<SystemLinkStatus> {
  return request<SystemLinkStatus>("/system-link/status");
}

export function startSystemLinkPairing(): Promise<PairingStart> {
  return request<PairingStart>("/system-link/pair/start", { method: "POST", body: "{}" });
}

export function getPendingSystemLinkPairings(): Promise<PendingPairing[]> {
  return request<PendingPairing[]>("/system-link/pair/pending");
}

export function approveSystemLinkPairing(pairingId: string, grantedCapabilities: string[]): Promise<LinkedSystemModule> {
  return request<LinkedSystemModule>(`/system-link/pair/${encodeURIComponent(pairingId)}/approve`, {
    method: "POST",
    body: JSON.stringify({ granted_capabilities: grantedCapabilities }),
  });
}

export function runModuleLifecycleAction(
  moduleId: string,
  action: ModuleLifecycleAction,
): Promise<LifecycleResult | LinkedSystemModule> {
  return request<LifecycleResult | LinkedSystemModule>(
    `/system-link/modules/${encodeURIComponent(moduleId)}/${action}`,
    { method: "POST", body: "{}" },
  );
}
