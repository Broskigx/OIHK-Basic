# OIHK Basic — Architecture

## Boundary

OIHK Basic is a local-first, single-user desktop product. It owns its repository, runtime, SQLite database, managed files, settings and release artifacts. It does not read from or import OIHKv at runtime.

```text
Tauri 2 desktop lifecycle
  └─ React + TypeScript + Vite
       ├─ product shell, workspace routes and the Copilot dock
       ├─ Canvas 2D graph engine
       └─ typed REST client
            └─ FastAPI sidecar on dynamic 127.0.0.1 port
                 ├─ SQLAlchemy async + SQLite
                 ├─ managed evidence storage
                 ├─ deterministic OSINT services
                 ├─ agent tool dispatch over the existing routes
                 └─ optional private/local model adapters
```

## Trust boundaries

Four, and they are not the same line:

1. **The OS account.** Everything below it is inside. A hostile process running
   as the same user is out of scope and covered only by the account boundary.
2. **The loopback port.** A network attacker cannot reach it. A *browser* can,
   which is why `Host` and `Origin` are validated on every request rather than
   left to CORS — see `THREAT_MODEL.md` T4.11 and T4.12.
3. **Third-party data.** Sources, OSINT answers and ingested pages are hostile
   text. They are size-bounded on the way in, never executed, and never fed
   back into the model.
4. **The module process.** A System Link module is a separate installation with
   its own data. It authenticates per call with a signed, timestamped envelope
   bound to a paired Ed25519 identity.

## Desktop lifecycle

Tauri selects an unused loopback port, starts the PyInstaller sidecar, exposes the selected endpoint to the frontend and monitors `/health`. Release builds bundle the sidecar through Tauri `externalBin`. No shell plugin or arbitrary process capability is exposed to web content.

The frontend asks Tauri for the live port before rendering, updates its REST/WebSocket base URL and waits for backend health. Closing the window terminates and reaps the managed child.

System Link module lifecycle remains behind the FastAPI control plane. It can launch only a module whose installer root, relative executable identity, package hash and executable hash match its signed manifest, and whose package carries a publisher signature verifying against an embedded trust anchor. Trust comes from that signature rather than from a built-in list of permitted module ids: a name check excluded honest modules while stopping nobody able to forge the signature. It never passes a manifest string to a shell.

## Frontend

- `frontend/src/App.tsx`: application composition and workspace orchestration.
- `frontend/src/app/`: routing, navigation, shell and design system.
- `frontend/src/features/`: dashboard, investigations, graph, entities, timeline, OSINT, custody, reports, Copilot, models, sources, settings, updates, onboarding and About.
- `frontend/src/graph/`: renderer, interaction, layouts, camera, hit testing and state/history.
- `frontend/src/api.ts`: typed requests, downloads and dynamic API endpoint.

Hash routes preserve direct access to case workspaces. Operational controls call real APIs or navigate to a complete workflow; unavailable adapters are shown explicitly rather than simulated.

Core routes remain a closed union. Verified module categories use `module:<module-id>:<category-id>` ids and are merged into navigation only while their runtime is authenticated `READY`/`BUSY` and `ui.navigation.register` is granted.

## Backend

- `app/models.py` and `app/schemas.py`: explicit persistence and API contracts.
- `app/routers/`: case lifecycle, graph workspace/snapshots, the evidence custody register, reports, OSINT history, local models, conversations and settings. Forensic acquisition and analysis are not here: they live in OIHK Evidence Lab and reach these records through the signed System Link module API.
- `app/services/evidence_storage.py`: atomic writes, safe paths and SHA-256 for bytes a linked module hands over.
- `app/services/managed_evidence.py`: path containment and re-hashing a held file against its seal.
- `app/services/local_models.py`: LM Studio, Ollama and OpenAI-compatible private endpoints.
- `app/database.py`: SQLite initialization, FK enforcement, additive migration and backup.
- `app/system_link/`: System Link v1 protocol, installation identity, pairing, registry, grants, package/runtime verification, lifecycle and module APIs.
- `app/core/first_run.py`: atomic OS-managed secret generation.
- `app/services/assistant_tools.py`: the operations the local Agent may invoke.

## Local Agent

The model does not reach the database, the filesystem or the network. It
returns a JSON envelope naming a tool from a fixed allowlist, and the dispatcher
calls the *existing route* with the real authenticated user — so every
authorization rule is inherited rather than reimplemented, and a route that
gains a new check gains it for the Agent at the same moment.

The allowlist is the boundary that matters. It excludes evidence mutation,
deletion of anything, and report approval: the Agent can draft, it cannot
destroy or attest. A turn is one model call and at most four tool calls, and
tool results are never fed back into the model — the reply is assembled
deterministically from tool summaries. That is what keeps text ingested from a
hostile page or registry response from steering a following call.

Mutating tools additionally require a keyword match against the user's own
message. That bounds an over-eager model and is not a security control; it does
not understand negation. What contains a wrong call is the allowlist, the
inherited authorization, and the audit record written under the acting user.

## Persistence

SQLite is the source of truth for cases, sources, entities, relationships, activity, evidence metadata, report documents/templates, OSINT queries, graph workspaces/snapshots, application settings, model configuration and Copilot conversations/messages.

System Link stores public installation identity, paired module identities/manifests, grants, lifecycle state, pairing/replay nonces and redacted events in dedicated tables. Private installation keys never enter SQLite.

Managed binary data is stored below the OS application-data directory. Evidence paths are resolved against that root before read, hash, preview or deletion. Graph camera and node positions are persisted per case.

## Network behavior

The backend binds to `127.0.0.1` by default and refuses a non-loopback bind while authentication is disabled. External traffic occurs only through user-triggered OSINT adapters or a user-configured local/private model endpoint. Public model endpoints and embedded endpoint credentials are rejected.

## Edition boundary

Basic excludes organizations, collaboration, cloud sync, licensing, billing, private connector control planes, Redis, queues and distributed deployment. Legacy organization columns may remain as internal compatibility partitions, but are not exposed as product features.
