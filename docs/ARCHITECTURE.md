# OIHK Basic — Architecture

## Boundary

OIHK Basic is a local-first, single-user desktop product. It owns its repository, runtime, SQLite database, managed files, settings and release artifacts. It does not read from or import OIHKv at runtime.

```text
Tauri 2 desktop lifecycle
  └─ React + TypeScript + Vite
       ├─ product shell and 11 workspaces
       ├─ Canvas 2D graph engine
       └─ typed REST client
            └─ FastAPI sidecar on dynamic 127.0.0.1 port
                 ├─ SQLAlchemy async + SQLite
                 ├─ managed evidence storage
                 ├─ deterministic OSINT/forensic services
                 └─ optional private/local model adapters
```

## Desktop lifecycle

Tauri selects an unused loopback port, starts the PyInstaller sidecar, exposes the selected endpoint to the frontend and monitors `/health`. Release builds bundle the sidecar through Tauri `externalBin`. No shell plugin or arbitrary process capability is exposed to web content.

The frontend asks Tauri for the live port before rendering, updates its REST/WebSocket base URL and waits for backend health. Closing the window terminates and reaps the managed child.

System Link module lifecycle remains behind the FastAPI control plane. It can launch only a first-party catalog entry whose installer root, relative executable identity, package hash and executable hash match its signed manifest. It never passes a manifest string to a shell.

## Frontend

- `frontend/src/App.tsx`: application composition and workspace orchestration.
- `frontend/src/app/`: routing, navigation, shell and design system.
- `frontend/src/features/`: dashboard, investigations, graph, OSINT, evidence, reports, Copilot, models, sources, settings, onboarding and About.
- `frontend/src/graph/`: renderer, interaction, layouts, camera, hit testing and state/history.
- `frontend/src/api.ts`: typed requests, downloads and dynamic API endpoint.

Hash routes preserve direct access to case workspaces. Operational controls call real APIs or navigate to a complete workflow; unavailable adapters are shown explicitly rather than simulated.

Core routes remain a closed union. Verified module categories use `module:<module-id>:<category-id>` ids and are merged into navigation only while their runtime is authenticated `READY`/`BUSY` and `ui.navigation.register` is granted.

## Backend

- `app/models.py` and `app/schemas.py`: explicit persistence and API contracts.
- `app/routers/`: case lifecycle, graph workspace/snapshots, evidence, reports, OSINT history, local models, conversations, settings and legacy forensic flows.
- `app/services/managed_evidence.py`: streaming, size limits, safe paths, atomic writes and SHA-256.
- `app/services/local_models.py`: LM Studio, Ollama and OpenAI-compatible private endpoints.
- `app/database.py`: SQLite initialization, FK enforcement, additive migration and backup.
- `app/system_link/`: System Link v1 protocol, installation identity, pairing, registry, grants, package/runtime verification, lifecycle and module APIs.
- `app/core/first_run.py`: atomic OS-managed secret generation.

## Persistence

SQLite is the source of truth for cases, sources, entities, relationships, activity, evidence metadata, report documents/templates, OSINT queries, graph workspaces/snapshots, application settings, model configuration and Copilot conversations/messages.

System Link stores public installation identity, paired module identities/manifests, grants, lifecycle state, pairing/replay nonces and redacted events in dedicated tables. Private installation keys never enter SQLite.

Managed binary data is stored below the OS application-data directory. Evidence paths are resolved against that root before read, hash, preview or deletion. Graph camera and node positions are persisted per case.

## Network behavior

The backend binds to `127.0.0.1` by default and refuses a non-loopback bind while authentication is disabled. External traffic occurs only through user-triggered OSINT adapters or a user-configured local/private model endpoint. Public model endpoints and embedded endpoint credentials are rejected.

## Edition boundary

Basic excludes organizations, collaboration, cloud sync, licensing, billing, private connector control planes, Redis, queues and distributed deployment. Legacy organization columns may remain as internal compatibility partitions, but are not exposed as product features.
