# OIHK Basic completion plan

Last updated: 2026-07-23

## Product boundary

OIHK Basic is the local-first, single-user community edition. It owns its own repository, runtime, data directory, database, desktop shell and release artifacts. It must not import source files from OIHKv at runtime and it does not expose enterprise collaboration, licensing, organization administration, cloud synchronization, private connectors or distributed infrastructure.

The working repository is `Broskigx/OIHK-Basic`. The old `OIHKv/OIHK-Basic` directory was an unversioned 5.4 GB working copy. Only its source and packaging files were migrated into this repository; `.env`, dependency folders, build output, logs, caches, local databases and local evidence were deliberately excluded.

## Initial state found

- GitHub contained one initial commit with 108 tracked files, 19 frontend source files, 78 backend Python files, one backend test and no Tauri shell.
- The unversioned working copy contained 69 frontend source files, 79 backend Python files, 15 test files and a configured Tauri 2 shell, but also generated dependencies and build artifacts.
- Of 208 source/configuration files in the migrated tree, 154 paths also exist in OIHKv and 46 were byte-identical at audit time. These files are now owned copies inside Basic; no fragile cross-repository imports exist.
- Frontend production build and TypeScript compilation passed: 1,626 modules and a 254.99 kB main JavaScript chunk before the completion work.
- Frontend lint failed with 25 errors.
- Frontend tests reported 30 passed and 2 failed because dashboard tests and implementation had diverged.
- Backend smoke tests reported 2 passed.
- Root portability tests reported 10 passed, 1 skipped and 9 import errors because the backend package was not placed on `sys.path`.
- Ruff reported 72 lint errors and 31 files requiring formatting.
- `cargo check` passed for the Tauri shell.
- No developer-specific path, username, Codex metadata or private MCP configuration was found in source files.
- A local `.env` existed only in the discarded working copy and was not migrated.
- Documentation was stale and contained mojibake; it incorrectly claimed that desktop and local AI were absent.
- Several copied data-model fields still used the name `organization_id`. They currently act as an internal single-user partition, not an enterprise feature, and will be hidden from the Basic user experience.
- Visible dead controls were found in the global search and dashboard graph toolbar.
- Navigation lacked dedicated OSINT, Local Models, Data Sources and About destinations.
- Local model configuration and stable chat persistence were incomplete.

## Architecture retained

### Desktop

- Tauri 2 owns application lifecycle and starts the packaged FastAPI sidecar.
- The backend binds only to `127.0.0.1` and uses a dynamically selected port in desktop mode.
- PyInstaller produces a per-platform sidecar. Tauri/NSIS produces the Windows installer.

### Frontend

- React, TypeScript and Vite.
- A compact dark OIHK design system centralized in CSS tokens.
- Hash-based local routing with lazy-loaded workspaces.
- A purpose-built Canvas 2D graph engine with separate store, renderer, camera, interaction, layout and spatial modules.

### Backend

- FastAPI with strict Pydantic schemas.
- SQLAlchemy async ORM backed by local SQLite.
- Local managed storage for evidence and imported files.
- REST-only API; no GraphQL, Redis, cloud queue or enterprise control plane.
- Local model adapters restricted to LM Studio, Ollama and manually configured loopback endpoints.

### Persistence

- SQLite is the source of truth for investigations, entities, relations, sources, evidence and activity.
- Small UI preferences and graph viewport state may use versioned local storage.
- Secrets are generated on first run in the OS application configuration directory.
- Application data and configuration use OS-specific directories and never require a developer path.

## Functionality to preserve

- Local investigations and case detail.
- Entity and relationship management.
- Intelligence graph, analytics, layouts and exports.
- OSINT lookups using legitimate public/local adapters.
- Evidence hashing, MIME detection, IOC extraction, custody metadata and safe storage.
- Timeline, reports, notes/sources and JSON portability.
- Local authentication and first-run secret generation.
- Tauri desktop packaging and per-platform build scripts.

## Functionality to remove or hide

- Empty buttons and decorative controls without a real action.
- “Professional” upgrade language inside operational workflows.
- Organization/team/enterprise wording in the user interface.
- Cloud AI assumptions and provider-specific cloud defaults.
- Brave or external search configuration as a required dependency.
- Active HTML previews, arbitrary shell execution and automatic external-link opening.
- Demo records or fabricated metrics in production storage.

## Missing or incomplete functionality

- First-run onboarding and optional rerun.
- Versioned application settings with backup/restore and sanitized diagnostics.
- Dedicated Local Models, Data Sources and About pages.
- Stable persisted copilots conversations with cancellation and no phantom chats.
- Model discovery, health checks and task-role assignment for LM Studio/Ollama.
- Complete investigation lifecycle: edit, duplicate, archive, restore and confirmed deletion.
- Graph workspace persistence, snapshots, undo/redo and provenance states.
- OSINT adapter registry with availability, cancellation and normalized results.
- Evidence manifest export and re-verification.
- Report templates and safe HTML/JSON exports.
- Automated E2E/smoke coverage and a repeatable Windows package build.

## Implementation phases

1. Baseline: import the advanced source tree, repair encoding, lint, formatting, unit tests and test discovery.
2. Security and portability: generated secrets, OS-specific paths, loopback-only endpoints, safe files, sanitized diagnostics and a repository secret scan.
3. Product shell: complete navigation, centralized tokens, functional global search and first-run onboarding.
4. Persistence: versioned frontend repositories plus backend schema/migration support for settings, models, chat and graph workspace data.
5. Workspaces: finish Overview, Investigations, Graph, OSINT, Evidence, Reports, Copilot, Local Models, Data Sources, Settings and About.
6. Desktop: reliable sidecar discovery, first-run lifecycle, update-safe data paths and Windows installer.
7. Quality: unit/integration tests, primary E2E flow, startup smoke test, responsive/keyboard review, packaging and documentation.

## Acceptance criteria

- A clean machine can install and launch OIHK Basic without Python, Node.js, cloud credentials or a user account with OIHK.
- The application remains useful when no local model is installed.
- LM Studio and Ollama can be discovered, tested and configured without hardcoded model names.
- Investigations, conversations and graph positions survive restart.
- No visible operational button is inert.
- No production metric is fabricated and demo data is opt-in and isolated.
- Evidence is never executed and its integrity can be verified after ingestion.
- All network destinations are explicit; defaults are loopback-only except user-triggered OSINT lookups.
- Build, TypeScript, ESLint, Ruff, backend tests, frontend tests, portability tests, Tauri checks and secret scanning pass.
- The Windows package build produces an installer whose contents exclude secrets, caches, repositories, models and developer data.

## Progress

- [x] Locate and isolate the correct Basic repository.
- [x] Audit the original Git state and advanced working copy.
- [x] Migrate source without local secrets or generated artifacts.
- [x] Record the initial build, lint, test and Tauri baseline.
- [x] Repair all baseline quality failures.
- [x] Complete the product workspaces and local-model flow.
- [x] Complete persistence, onboarding and diagnostics.
- [x] Complete Windows installer and managed-sidecar smoke testing.
- [x] Complete security, dependency, responsive-layout and interaction review.
- [ ] Publish the final Basic branch and release-ready documentation.
