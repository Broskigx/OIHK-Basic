# Local ↔ Remote Sync Audit — OIHK Basic 0.1.1-alpha.2

> Date: 2026-07-31 · Prepared on branch `agent/secure-auto-updater` · Integration branch: `release/0.1.1-alpha.2`
> Remote: `Broskigx/OIHK-Basic` (`origin`)

This document records the full comparison between the local repository state and
`origin/master`, the risks identified, and the integration plan used to prepare
the `0.1.1-alpha.2` release candidate without losing any security, updater,
packaging or smoke-testing work already present on GitHub.

## 1. Baseline state

| Item | Value |
| --- | --- |
| Current branch (start) | `agent/secure-auto-updater` |
| Local `HEAD` SHA | `d5b9305532fd5fa73ce383cdd5b90aa7c3b7b308` |
| `origin/master` SHA | `d2862e59ce3aafb9a243f2f6134ec309cf9d12de` |
| Merge base (`origin/master` ↔ `HEAD`) | `d5b9305` (= local `HEAD`) |
| Local `master` | `ce4053e` (initial commit, 20 commits behind `origin/master`) |
| Tree state (start) | 18 modified files, 7 untracked files, no staged changes |
| Canonical version (start) | `VERSION` = `0.1.0` (all surfaces); `origin/master` = `0.1.1-alpha.1` |
| Tags on remote | `basic-v0.1.1-alpha.1` |

**Key topology finding:** `origin/master` is **ahead** of the local branch
(merge base = local `HEAD`). Everything committed on `agent/secure-auto-updater`
is already contained in `origin/master` via merge PR #2. The local-only work is
entirely **uncommitted** (working tree + untracked files), i.e. the Copilot
streaming work, the Canvas layout optimization, the new documentation set and
the local/unsigned build mode.

## 2. What exists only on `origin/master` (must be preserved)

These commits/features exist remotely and must never be lost during integration:

- Signed auto-updater implementation (Tauri updater, Minisign, pre-update SQLite
  backup protocol, one-use sidecar shutdown token).
- Evidence integrity and investigation workflow hardening (`d72cc82`).
- Reproducible alpha packaging and updater gates (`75ca533`): `requirements.lock`
  (Windows x64 Python 3.11 lock), `verify_update_signature` example, `smoke-installer.ps1`,
  `CARGO_BUILD_JOBS=1` default.
- Gitleaks scanning of complete history with `.gitleaks.toml` (`ef45483`, `c664e51`).
- Multi-job CI (`ci.yml`): Gitleaks + backend matrix (Ubuntu/Windows) + frontend
  Node 22 + desktop Rust/Tauri jobs.
- Public README wording: source-only unstable preview, LM Studio as the current
  validated backend, Node.js 22 requirement, alpha stability warnings
  (`8b6af70`, `bf55e3c`, `d2862e5`).
- Version `0.1.1-alpha.1` across all version surfaces + `CHANGELOG.md` entry.

## 3. What exists only locally (to be integrated)

### Uncommitted modifications (18 files)

| File | Change |
| --- | --- |
| `.github/workflows/ci.yml`, `.github/workflows/release-windows.yml` | Ruff with `--config backend/pyproject.toml` |
| `backend/app/database_migrations.py` | Migration 4 (conversation `model`/`settings`) + ALTER guard refactor (skip existing columns, missing tables) |
| `backend/app/models.py` | `AssistantConversation.model`, `.settings` |
| `backend/app/routers/assistant.py` | SSE streaming endpoint, bounded retries, empty-title/content validation |
| `backend/app/schemas.py` | `ConversationCreate/Update/Read` `model` + `settings` |
| `backend/app/services/local_models.py` | `stream()`/`stream_complete()` for OpenAI-compatible + Ollama providers |
| `backend/tests/test_copilot_conversations.py` | Chat create/save/open, chat isolation, rename/archive, SSE stream tests |
| `docs/BUILDING.md` | Local unsigned build mode, signed alpha mode, Node 22, artifact names |
| `frontend/package.json` | Scripts `check`, `tauri:build`, `release:local`, `release:alpha` |
| `frontend/src/api.ts`, `src/components/graphTypes.ts`, `src/features/copilot/CopilotWorkspaceView.tsx`, `src/types.ts` | Copilot streaming client, full entity type set |
| `frontend/src/graph/layout.ts` | Packed numeric spatial-grid keys, canonical cell-pair iteration (no `Set<string>` per tick) |
| `frontend/src/graph/renderer.ts` | LOD/visible-node limit usage |
| `scripts/build-windows.ps1` | `-Channel local`, `-Unsigned`, `-SkipUpdater`, `$BuildStarted` stale-artifact check, local vs signed separation |
| `tests/test_separation.py` | Expanded separation assertions |

### Untracked files (7)

| File | Note |
| --- | --- |
| `PRIVACY.md`, `THREAT_MODEL.md`, `RESPONSIBLE_USE.md` | Required security/documentation set (missing on GitHub) |
| `OIHK_AUDIT.md` | Audit report driving the alpha.2 fixes |
| `backend/.env.example` | Documented environment variables |
| `frontend/src/graph/performance.test.ts` | Graph performance regression tests (50/500/2500 nodes) |
| `src-tauri/tauri.local.conf.json` | Local build overlay: `createUpdaterArtifacts: false` |

## 4. Overwrite risks

- **No destructive operations used:** no `git reset --hard`, no `git clean -fd`,
  no `git push --force`.
- Working tree backed up to `/tmp/oihk-release/` (`worktree.diff`, `untracked.txt`,
  `untracked/` copy) before any branch operation.
- Local uncommitted work was preserved via `git stash push -u`, then reapplied
  with a 3-way merge on the new branch (`git stash pop`). Nothing was dropped.
- Merge conflicts occurred in exactly two files and were resolved manually:

### Conflict resolution

1. `.github/workflows/ci.yml`
   - Kept master's multi-job CI (Gitleaks, backend matrix, frontend, desktop) and
     `requirements.lock`-based installs.
   - Kept the local Ruff invocation with `--config backend/pyproject.toml`
     (matches `release-windows.yml` and `scripts/build-windows.ps1`).
2. `scripts/build-windows.ps1`
   - Kept master's `$RequirementsLock` (hash-pinned installs) **and** local
     `$BuildStarted` (stale-installer guard).
   - Kept master's `verify_update_signature`, `smoke-installer.ps1`,
     `CARGO_BUILD_JOBS=1` and local `-Channel local`/`-Unsigned`/`-SkipUpdater`
     unsigned-build mode.

## 5. Version divergence (Fase 3)

| Surface | Before | After |
| --- | --- | --- |
| `VERSION` | `0.1.0` (local) / `0.1.1-alpha.1` (master) | `0.1.1-alpha.2` |
| `frontend/package.json` | `0.1.0` / `0.1.1-alpha.1` | `0.1.1-alpha.2` |
| `frontend/package-lock.json` | `0.1.0` | `0.1.1-alpha.2` |
| `src-tauri/tauri.conf.json` | `0.1.0` / `0.1.1-alpha.1` | `0.1.1-alpha.2` |
| `src-tauri/Cargo.toml`, `Cargo.lock` | `0.1.0` / `0.1.1-alpha.1` | `0.1.1-alpha.2` |
| `backend/pyproject.toml` | `0.1.0` / `0.1.1-alpha.1` | `0.1.1-alpha.2` |
| `backend/app/version.py` | `0.1.0` | `0.1.1-alpha.2` |
| `frontend/src/version.ts` | `0.1.0` | `0.1.1-alpha.2` |
| `CHANGELOG.md` | `0.1.1-alpha.1` entry | `+ 0.1.1-alpha.2` entry |
| Installer metadata / docs | `0.1.0`, `0.1.1-alpha.1` refs | `0.1.1-alpha.2` refs (BUILDING, LINUX/MACOS/WINDOWS install docs, RELEASE_CHECKLIST, RELEASING) |

Run with: `python scripts/version.py sync` then `python scripts/version.py check`
(gate: **do not continue** on divergent version).

## 6. Contradiction fixes

- **README vs CHANGELOG:** README now states the experimental `0.1.1-alpha.2`
  candidate is the only public distribution (prerelease for testers), consistent
  with the CHANGELOG candidate entries.
- **README vs BUILDING.md (Node):** all docs now require Node.js 22 (matches
  `frontend/package.json` `engines` `>=22 <23` and CI `node-version: "22"`).
- **README vs KNOWN_LIMITATIONS (Ollama):** LM Studio is the validated backend;
  Ollama/other OpenAI-compatible endpoints exist in code but are not guaranteed
  in this preview — wording aligned across `README.md`, `docs/KNOWN_LIMITATIONS.md`
  and the CHANGELOG.
- **Version references:** installer artifact names and upgrade fixtures updated
  to `0.1.1-alpha.2`; historical upgrade fixture (`0.1.0 → 0.1.1-alpha.1`) kept
  as-is because it tests the real upgrade path.

## 7. Integration plan (executed)

1. Inspect local + remote state (Section 1).
2. Backup working tree; `git stash push -u`.
3. `git checkout -b release/0.1.1-alpha.2 origin/master`.
4. `git stash pop`; resolve the two conflicts manually (Section 4).
5. Version sync: `VERSION` → `0.1.1-alpha.2`, `python scripts/version.py sync`,
   add CHANGELOG entry, `python scripts/version.py check`.
6. Verify Canvas layout optimization and `performance.test.ts` are present.
7. Fix doc contradictions (Section 6).
8. Run full validation (backend + frontend + Rust + version).
9. Commit the candidate on `release/0.1.1-alpha.2` (no push, no release).

## 8. Post-integration validation status

| Gate | Status |
| --- | --- |
| `python scripts/version.py check` | ✅ synchronized `0.1.1-alpha.2` |
| Ruff (`--config backend/pyproject.toml`) | ✅ passed |
| `pytest backend/tests tests` | ✅ 79 passed, 1 skipped |
| `npm run lint` / `npm test -- --run` / `npm run build` | ✅ lint clean · 46 passed · build OK |
| `cargo fmt --check` / `cargo check --locked` (default + `updater-release`) | ✅ passed |
| Gitleaks / dependency audits | ✅ unchanged (CI-only) |
