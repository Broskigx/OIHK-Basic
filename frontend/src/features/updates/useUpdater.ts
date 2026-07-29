import { useCallback, useEffect, useReducer, useRef } from "react";
import type { Update } from "@tauri-apps/plugin-updater";
import { prepareDesktopUpdate, resumeDesktopUpdate } from "../../api";
import {
  initialUpdateState,
  isPublishedUpdateChannel,
  sanitizedUpdateError,
  updateReducer,
} from "./updateMachine";

export type UpdateController = ReturnType<typeof useUpdater>;

function isDesktop(): boolean {
  return "__TAURI_INTERNALS__" in window;
}

export function useUpdater(
  autoCheck: boolean,
  channel: "alpha" | "beta" | "stable",
  updaterEnabled: boolean,
) {
  const [state, dispatch] = useReducer(updateReducer, initialUpdateState);
  const updateRef = useRef<Update | null>(null);
  const tokenRef = useRef("");
  const cancelRef = useRef(false);
  const checkedAutomatically = useRef(false);
  const supported = isDesktop() && updaterEnabled;

  const fail = useCallback((cause: unknown) => {
    const error = sanitizedUpdateError(cause);
    dispatch({ type: "ERROR", ...error });
  }, []);

  const checkForUpdates = useCallback(async () => {
    if (!supported) return;
    if (!isPublishedUpdateChannel(channel)) {
      dispatch({
        type: "ERROR",
        code: "channel_not_configured",
        message: `The ${channel} channel is reserved but is not published yet. Select alpha to check now.`,
      });
      return;
    }
    dispatch({ type: "CHECK" });
    try {
      await updateRef.current?.close();
      const { check } = await import("@tauri-apps/plugin-updater");
      const update = await check({ timeout: 15_000 });
      updateRef.current = update;
      if (!update) {
        dispatch({ type: "CURRENT" });
        return;
      }
      dispatch({
        type: "AVAILABLE",
        version: update.version,
        currentVersion: update.currentVersion,
        notes: update.body,
        date: update.date,
      });
    } catch (cause) {
      fail(cause);
    }
  }, [channel, fail, supported]);

  useEffect(() => {
    if (!autoCheck || checkedAutomatically.current || !supported) return;
    checkedAutomatically.current = true;
    void checkForUpdates();
  }, [autoCheck, checkForUpdates, supported]);

  const download = useCallback(async () => {
    const update = updateRef.current;
    if (!update) return;
    cancelRef.current = false;
    try {
      await update.download((event) => {
        if (event.event === "Started") {
          dispatch({ type: "DOWNLOAD_STARTED", total: event.data.contentLength });
        } else if (event.event === "Progress") {
          dispatch({ type: "DOWNLOAD_PROGRESS", bytes: event.data.chunkLength });
        } else {
          dispatch({ type: "VERIFY" });
        }
      });
      if (cancelRef.current) return;
      dispatch({ type: "PREPARE_BACKUP" });
      const prepared = await prepareDesktopUpdate(update.version, channel);
      if (cancelRef.current) {
        await resumeDesktopUpdate();
        dispatch({ type: "DEFER" });
        return;
      }
      tokenRef.current = prepared.update_token;
      dispatch({ type: "READY", backupPath: prepared.backup_path });
    } catch (cause) {
      if (cancelRef.current) {
        dispatch({ type: "DEFER" });
      } else {
        fail(cause);
      }
    }
  }, [channel, fail]);

  const install = useCallback(async () => {
    const update = updateRef.current;
    const token = tokenRef.current;
    if (!update || !token) return;
    dispatch({ type: "INSTALL" });
    try {
      const { invoke } = await import("@tauri-apps/api/core");
      await invoke("stop_backend_for_update", { updateToken: token });
      await update.install();
    } catch (cause) {
      try {
        const { invoke } = await import("@tauri-apps/api/core");
        await invoke("restart_backend_after_update_failure");
        await resumeDesktopUpdate();
      } catch {
        // Recovery information remains on disk for the next launch.
      }
      fail(cause);
    }
  }, [fail]);

  const defer = useCallback(async () => {
    cancelRef.current = true;
    const preparationRunning = state.phase === "preparing_backup";
    tokenRef.current = "";
    try {
      await updateRef.current?.close();
      if (!preparationRunning) await resumeDesktopUpdate();
    } catch {
      // Deferral is still safe: installation is never called.
    }
    dispatch({ type: "DEFER" });
  }, [state.phase]);

  const openBackupFolder = useCallback(async () => {
    if (!isDesktop()) return;
    const { invoke } = await import("@tauri-apps/api/core");
    await invoke("open_backup_directory");
  }, []);

  return {
    state,
    supported,
    checkForUpdates,
    download,
    install,
    defer,
    openBackupFolder,
  };
}
