import { useCallback, useEffect, useMemo, useState } from "react";
import type { NavigationItem } from "../app/navigation";
import { isModuleRouteId } from "../app/navigation";
import {
  approveSystemLinkPairing,
  getPendingSystemLinkPairings,
  getSystemLinkStatus,
  runModuleLifecycleAction,
  startSystemLinkPairing,
} from "./api";
import type {
  LinkedSystemModule,
  ModuleLifecycleAction,
  PairingStart,
  PendingPairing,
  SystemLinkStatus,
} from "./types";

export function buildModuleNavigation(modules: readonly LinkedSystemModule[]): NavigationItem[] {
  return modules
    .filter((module) => module.enabled && (module.state === "READY" || module.state === "BUSY"))
    .flatMap((module) =>
      module.categories
        .flatMap((category): NavigationItem[] => {
          if (!category.enabled || !isModuleRouteId(category.route_id)) return [];
          return [{
            id: category.route_id,
            label: category.label,
            caseScoped: category.case_scoped,
            group: "linked-modules",
            icon: category.icon,
            moduleId: module.module_id,
            order: category.order,
          }];
        }),
    )
    .sort((left, right) => (left.order ?? 0) - (right.order ?? 0));
}

export function useSystemLinkRegistry() {
  const [status, setStatus] = useState<SystemLinkStatus | null>(null);
  const [pending, setPending] = useState<PendingPairing[]>([]);
  const [pairing, setPairing] = useState<PairingStart | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyModule, setBusyModule] = useState("");
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [nextStatus, nextPending] = await Promise.all([
        getSystemLinkStatus(),
        getPendingSystemLinkPairings(),
      ]);
      setStatus(nextStatus);
      setPending(nextPending);
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "System Link status is unavailable");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!pairing && !status?.modules.some((module) => ["STARTING", "AUTHENTICATING", "READY", "BUSY", "STOPPING"].includes(module.state))) return;
    const timer = window.setInterval(() => void refresh(), 3000);
    return () => window.clearInterval(timer);
  }, [pairing, refresh, status]);

  const moduleNavigation = useMemo(() => buildModuleNavigation(status?.modules ?? []), [status?.modules]);

  const runAction = useCallback(async (moduleId: string, action: ModuleLifecycleAction) => {
    setBusyModule(moduleId);
    setError("");
    try {
      await runModuleLifecycleAction(moduleId, action);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : `Could not ${action} module`);
      await refresh();
    } finally {
      setBusyModule("");
    }
  }, [refresh]);

  const beginPairing = useCallback(async () => {
    setError("");
    try {
      setPairing(await startSystemLinkPairing());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not create OIHK Link Key");
    }
  }, []);

  const approvePairing = useCallback(async (pairingId: string, capabilities: string[]) => {
    setError("");
    try {
      await approveSystemLinkPairing(pairingId, capabilities);
      setPairing(null);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not approve module pairing");
    }
  }, [refresh]);

  return {
    status,
    pending,
    pairing,
    loading,
    busyModule,
    error,
    moduleNavigation,
    refresh,
    runAction,
    beginPairing,
    approvePairing,
  };
}
