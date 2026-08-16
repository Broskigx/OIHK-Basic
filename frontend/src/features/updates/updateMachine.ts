type UpdatePhase =
  | "idle"
  | "checking"
  | "current"
  | "available"
  | "downloading"
  | "verifying"
  | "preparing_backup"
  | "ready_to_restart"
  | "installing"
  | "deferred"
  | "error";

export type UpdateState = {
  phase: UpdatePhase;
  currentVersion: string;
  targetVersion: string;
  notes: string;
  publishedAt: string;
  downloadedBytes: number;
  totalBytes: number;
  backupPath: string;
  errorCode: string;
  message: string;
};

export type UpdateAction =
  | { type: "CHECK" }
  | { type: "CURRENT" }
  | { type: "AVAILABLE"; version: string; currentVersion: string; notes?: string; date?: string }
  | { type: "DOWNLOAD_STARTED"; total?: number }
  | { type: "DOWNLOAD_PROGRESS"; bytes: number }
  | { type: "VERIFY" }
  | { type: "PREPARE_BACKUP" }
  | { type: "READY"; backupPath: string }
  | { type: "INSTALL" }
  | { type: "DEFER"; message?: string }
  | { type: "ERROR"; code: string; message: string };

export const initialUpdateState: UpdateState = {
  phase: "idle",
  currentVersion: "",
  targetVersion: "",
  notes: "",
  publishedAt: "",
  downloadedBytes: 0,
  totalBytes: 0,
  backupPath: "",
  errorCode: "",
  message: "",
};

export function updateReducer(state: UpdateState, action: UpdateAction): UpdateState {
  switch (action.type) {
    case "CHECK":
      return { ...initialUpdateState, phase: "checking", currentVersion: state.currentVersion };
    case "CURRENT":
      return { ...initialUpdateState, phase: "current", currentVersion: state.currentVersion };
    case "AVAILABLE":
      return {
        ...initialUpdateState,
        phase: "available",
        currentVersion: action.currentVersion,
        targetVersion: action.version,
        notes: action.notes ?? "",
        publishedAt: action.date ?? "",
      };
    case "DOWNLOAD_STARTED":
      return { ...state, phase: "downloading", totalBytes: action.total ?? 0, downloadedBytes: 0 };
    case "DOWNLOAD_PROGRESS":
      return { ...state, downloadedBytes: state.downloadedBytes + action.bytes };
    case "VERIFY":
      return { ...state, phase: "verifying" };
    case "PREPARE_BACKUP":
      return { ...state, phase: "preparing_backup" };
    case "READY":
      return { ...state, phase: "ready_to_restart", backupPath: action.backupPath };
    case "INSTALL":
      return { ...state, phase: "installing" };
    case "DEFER":
      return { ...state, phase: "deferred", message: action.message ?? "Update deferred. Your current version remains available." };
    case "ERROR":
      return { ...state, phase: "error", errorCode: action.code, message: action.message };
  }
}

export function compareSemver(left: string, right: string): number {
  const parse = (value: string) => {
    const match = value
      .replace(/^v/, "")
      .match(/^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$/);
    if (!match) throw new Error(`Invalid semantic version: ${value}`);
    return {
      numbers: [Number(match[1]), Number(match[2]), Number(match[3])],
      prerelease: match[4]?.split(".") ?? [],
    };
  };
  const a = parse(left);
  const b = parse(right);
  for (let index = 0; index < 3; index += 1) {
    const difference = (a.numbers[index] ?? 0) - (b.numbers[index] ?? 0);
    if (difference) return Math.sign(difference);
  }
  if (!a.prerelease.length && !b.prerelease.length) return 0;
  if (!a.prerelease.length) return 1;
  if (!b.prerelease.length) return -1;
  const length = Math.max(a.prerelease.length, b.prerelease.length);
  for (let index = 0; index < length; index += 1) {
    const leftPart = a.prerelease[index];
    const rightPart = b.prerelease[index];
    if (leftPart === undefined) return -1;
    if (rightPart === undefined) return 1;
    if (leftPart === rightPart) continue;
    const leftNumeric = /^\d+$/.test(leftPart);
    const rightNumeric = /^\d+$/.test(rightPart);
    if (leftNumeric && rightNumeric) {
      return Math.sign(Number(leftPart) - Number(rightPart));
    }
    if (leftNumeric) return -1;
    if (rightNumeric) return 1;
    return Math.sign(leftPart.localeCompare(rightPart));
  }
  return 0;
}

export function isPublishedUpdateChannel(
  channel: "alpha" | "beta" | "stable",
): boolean {
  return channel === "alpha";
}

export function sanitizedUpdateError(cause: unknown): { code: string; message: string } {
  const value = cause instanceof Error ? cause.message.toLowerCase() : String(cause).toLowerCase();
  if (value.includes("signature") || value.includes("public key")) {
    return { code: "invalid_signature", message: "The update signature is invalid. Installation was blocked." };
  }
  if (value.includes("space") || value.includes("disk full")) {
    return { code: "insufficient_space", message: "There is not enough disk space to stage this update." };
  }
  if (value.includes("backup")) {
    return { code: "backup_failed", message: "The verified pre-update backup could not be prepared." };
  }
  if (value.includes("shutdown") || value.includes("managed backend")) {
    return { code: "backend_stop_failed", message: "The local service could not be stopped safely. Installation was cancelled." };
  }
  if (value.includes("network") || value.includes("connect") || value.includes("timeout")) {
    return { code: "network_unavailable", message: "The update service is unavailable. Continue using the current version and retry later." };
  }
  return { code: "update_failed", message: "The update could not be completed safely. Your current version remains available." };
}
