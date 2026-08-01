# Changelog

## 0.1.1-alpha.2 — 2026-07-31

Second alpha candidate for testers: streaming Copilot, per-conversation model settings, a faster Canvas layout engine and a clear split between local unsigned builds and signed alpha releases.

### Added

- Server-Sent-Events (SSE) streaming for Copilot replies with incremental deltas, bounded retries and no lost user turns on disconnect.
- Per-conversation model and settings persistence (schema migration 4) so each chat remembers the model it was drafted with.
- Packed numeric spatial-grid keys in the Canvas layout engine: bijective cell packing, canonical cell-pair iteration and no per-tick string-keyed deduplication. Small graphs keep exact all-pairs repulsion.
- Graph performance regression tests for small, medium and large graphs (50/500/2500 nodes) plus spatial hit-test and fit-to-view coverage.
- `npm run check`, `npm run tauri:build`, `npm run release:local` (unsigned, no updater, no signing keys) and `npm run release:alpha` (signed updater), with `src-tauri/tauri.local.conf.json` keeping local builds updater-free.
- `PRIVACY.md`, `THREAT_MODEL.md` and `RESPONSIBLE_USE.md`, plus `OIHK_AUDIT.md` and `backend/.env.example`.
- Database migration runner now skips `ALTER TABLE ADD COLUMN` statements whose columns already exist on fresh databases.

### Security

- Copilot still talks only to loopback/private endpoints; streaming does not change the local-model trust boundary.
- Local unsigned builds cannot silently degrade into signed releases: missing signing keys fail the build with a clear message.

### Quality

- Version metadata synchronized to 0.1.1-alpha.2 across every build surface.
- Documentation aligned on Node.js 22 (matching `frontend/package.json` engines) and the current alpha/testing status.

## 0.1.1-alpha.1 — 2026-07-28

First public-alpha candidate for the standalone OIHK Basic desktop application.

### Added

- Separate local-first single-user repository, data directory and desktop runtime.
- Eleven complete product workspaces and eight-step optional onboarding.
- Premium Canvas 2D graph with persistent positions/camera, minimap, layouts, filters, multi-select, pinning, undo/redo and named snapshots.
- Full investigation lifecycle with versioned JSON portability.
- Explicit OSINT history and promotion workflow without automatic graph mutation.
- Managed evidence streaming, SHA-256 verification, provenance, manifest export and safe previews.
- Persistent report documents/templates with Markdown, sandboxed HTML, JSON and optional local-model drafts.
- Persistent Copilot conversations using only LM Studio, Ollama or private compatible endpoints.
- Versioned application settings, storage diagnostics and SQLite backups.
- Tauri 2 packaging with a bundled PyInstaller backend and Windows NSIS installer.
- Official Tauri 2 signed updater with explicit download/restart decisions, progress, release notes, safe deferral and alpha/beta/stable channel metadata.
- Mandatory pre-update SQLite checkpoint, verified online backup, SHA-256 metadata, write draining and one-use graceful sidecar shutdown.
- Formal checksum-protected `schema_migrations` history, migration backups and recovery status surfaced in Settings/About.
- Pinned CI/release workflows that gate draft prereleases on tests, lint, dependency audits, Gitleaks, PyInstaller smoke and artifact validation.

### Security

- Loopback enforcement for the default no-login desktop mode.
- Atomic first-run secrets and managed file writes.
- Private/local model endpoint validation and credential rejection in URLs.
- Restrictive webview/report CSP, safe error rendering and no exposed shell plugin.
- Bounded uploads/reads, path confinement, attachment-only unsafe previews and evidence hash re-verification.
- Updater private keys remain CI-only; invalid or absent signatures and incomplete artifacts fail closed.
- Public URL ingestion rejects credentials, private/local/reserved destinations, onion hosts and unsafe redirect hops while enforcing streamed response limits.
- Chain-of-custody verification rehashes managed evidence files and checks the per-case anchor for truncation.
- Packaged sidecars ignore working-directory `.env` files, use a fixed application-data working directory and exit if their Tauri parent disappears.
- Spreadsheet exports neutralize user-controlled formula cells, CSRF works in optional-auth mode, and OOXML extraction is bounded against decompression bombs.

### Quality

- Backend, frontend, graph performance, portability, packaging and installed-sidecar regression coverage.
- Correct direct hash routing for case workspaces.
- Adaptive spatial force layout for large graphs.
- Linear-time forensic entropy calculation with regression coverage for binary uploads.
