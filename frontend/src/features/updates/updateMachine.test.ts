import { describe, expect, it } from "vitest";
import {
  compareSemver,
  initialUpdateState,
  isPublishedUpdateChannel,
  sanitizedUpdateError,
  updateReducer,
} from "./updateMachine";

describe("update state machine", () => {
  it("requires an explicit restart after download and backup", () => {
    let state = updateReducer(initialUpdateState, {
      type: "AVAILABLE",
      version: "0.1.1",
      currentVersion: "0.1.0",
    });
    state = updateReducer(state, { type: "DOWNLOAD_STARTED", total: 100 });
    state = updateReducer(state, { type: "DOWNLOAD_PROGRESS", bytes: 40 });
    state = updateReducer(state, { type: "VERIFY" });
    state = updateReducer(state, { type: "PREPARE_BACKUP" });
    state = updateReducer(state, { type: "READY", backupPath: "safe.sqlite3" });
    expect(state.phase).toBe("ready_to_restart");
    expect(state.downloadedBytes).toBe(40);
    expect(state.backupPath).toBe("safe.sqlite3");
  });

  it("defers safely without entering installation", () => {
    const state = updateReducer(
      { ...initialUpdateState, phase: "downloading", targetVersion: "0.1.1" },
      { type: "DEFER" },
    );
    expect(state.phase).toBe("deferred");
  });

  it("compares stable and prerelease SemVer", () => {
    expect(compareSemver("0.1.1", "0.1.0")).toBe(1);
    expect(compareSemver("0.1.1-alpha.1", "0.1.1")).toBe(-1);
    expect(compareSemver("0.1.0", "0.1.0")).toBe(0);
    expect(compareSemver("0.1.1-alpha.10", "0.1.1-alpha.2")).toBe(1);
    expect(compareSemver("0.1.1-alpha.1", "0.1.1-alpha.beta")).toBe(-1);
    expect(compareSemver("0.1.1+build.5", "0.1.1+build.9")).toBe(0);
  });

  it("never exposes raw signature errors", () => {
    expect(sanitizedUpdateError(new Error("signature rejected at C:\\private\\path"))).toEqual({
      code: "invalid_signature",
      message: "The update signature is invalid. Installation was blocked.",
    });
  });

  it("maps recoverable endpoint, disk, and backup failures without raw details", () => {
    expect(sanitizedUpdateError(new Error("network timeout at https://private.invalid")).code).toBe(
      "network_unavailable",
    );
    expect(sanitizedUpdateError(new Error("disk full at C:\\Users\\private")).code).toBe(
      "insufficient_space",
    );
    expect(sanitizedUpdateError(new Error("backup failed: secret case title")).code).toBe(
      "backup_failed",
    );
  });

  it("retries from an error and exposes only the published alpha channel", () => {
    const retrying = updateReducer(
      { ...initialUpdateState, phase: "error", errorCode: "network_unavailable" },
      { type: "CHECK" },
    );
    expect(retrying.phase).toBe("checking");
    expect(retrying.errorCode).toBe("");
    expect(isPublishedUpdateChannel("alpha")).toBe(true);
    expect(isPublishedUpdateChannel("beta")).toBe(false);
    expect(isPublishedUpdateChannel("stable")).toBe(false);
  });
});
