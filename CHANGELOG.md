# Changelog

## 0.1.0 — 2026-07-23

Initial standalone OIHK Basic release candidate.

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

### Security

- Loopback enforcement for the default no-login desktop mode.
- Atomic first-run secrets and managed file writes.
- Private/local model endpoint validation and credential rejection in URLs.
- Restrictive webview/report CSP, safe error rendering and no exposed shell plugin.
- Bounded uploads/reads, path confinement, attachment-only unsafe previews and evidence hash re-verification.

### Quality

- Backend, frontend, graph performance, portability, packaging and installed-sidecar regression coverage.
- Correct direct hash routing for case workspaces.
- Adaptive spatial force layout for large graphs.
