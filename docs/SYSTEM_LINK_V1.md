# OIHK System Link v1 host foundation

OIHK Basic owns the local host/control plane. OIHK Evidence Lab remains a separate installation, process, repository, UI/domain implementation, and specialized data owner. There are no cross-repository source imports and Basic does not execute forensic code received from a module.

## Versioned contract

- System Link protocol: `1.0`
- Manifest schema: `1`
- Module SDK metadata version: `1`
- First approved host adapter: `oihk.evidence-lab`

The backend contract lives in `backend/app/system_link/`. The frontend registry and control surface live in `frontend/src/system-link/`.

## Trust and pairing

Basic creates an Ed25519 installation identity. Only its public key and SHA-256 fingerprint are stored in SQLite. The raw private key is protected by a selected storage provider, reported per installation through `key_storage`:

- Windows: user-bound DPAPI;
- macOS / Linux: the operating-system keyring (Keychain / Secret Service) through the standard `keyring` package, matching Evidence Lab;
- fallback (only when the OS keyring has no usable backend): AES-GCM wrapping plus a mode-`0600` file, with an explicit `encrypted-file` storage kind so operators can tell which provider actually protects the key.

`POST /system-link/pair/start` creates a 128-bit, five-minute OIHK Link Key and challenge. The database stores only the Link Key hash. `POST /system-link/pair/complete` validates every cryptographic and package property first, then consumes the key with a single atomic conditional update

```sql
UPDATE pairing_nonce SET used_at = ... WHERE id = ... AND used_at IS NULL AND expires_at > ... AND link_key_hash = ...
```

so two concurrent requests with the same key can never both succeed. The transaction rolls back on any post-claim failure, so a legitimate module can retry without burning its key (presenting a correct key with an invalid signature can never consume it). A host user must then approve a subset of the requested capabilities through `POST /system-link/pair/{id}/approve`, which flushes the parent module row before inserting capability grants so real SQLite FK enforcement never aborts approval.

The Link Key is single-use and never becomes a bearer credential. Later module-to-host calls use signed method/path/body/timestamp/nonce envelopes. Used nonces are persisted briefly and duplicate nonces fail closed.

## Publisher trust

Basic embeds a small, explicit and auditable set of OIHK first-party publisher trust anchors (Ed25519 public keys). A package is accepted only when `metadata/publisher.json` matches the signed v1 contract, the publisher-signed `content_sha256` matches the package on disk, and the Ed25519 signature verifies under the declared publisher key. Release packages must be signed by a key whose fingerprint is in the embedded `RELEASE_TRUST_ANCHORS`; development packages are accepted only when `OIHK_SYSTEM_LINK_ALLOW_DEV_PUBLISHERS=1` and are tagged with the `development` channel. Every failure path is fail-closed: invalid signature, unknown publisher, altered package or manifest, and unauthorized keys are all rejected before the Link Key is consumed. The release private key is never stored in any repository; the anchors include a key id and note to support rotation (add the successor anchor before switching, keep both during the transition window, then retire the old one).

## Registry and persistence

Schema migrations 6, 7 and 8 add explicit tables for:

- Basic's public installation identity;
- linked modules and signed manifests;
- capability grants;
- pending/used pairing challenges;
- replay nonces;
- redacted System Link audit events;
- publisher identity (key id and channel) recorded per linked module.

Runtime/link states are explicit: `NOT_INSTALLED`, `UNLINKED`, `PAIRING`, `LINKED_OFF`, `STARTING`, `AUTHENTICATING`, `READY`, `BUSY`, `STOPPING`, `ERROR`, `INCOMPATIBLE`, `REVOKED`, `DISABLED`, and `QUARANTINED`.

`LINKED_OFF` preserves module identity, manifest, package reference, pairing, and capability grants. Revocation is a separate transition and requires new pairing.

## Lifecycle security

The lifecycle descriptor supports only `managed-process`. It contains an installer-registered absolute root, a relative executable identity, an exact SHA-256, a fixed loopback runtime URL, and bounded timeouts. It rejects shells, interpreters, scripts, path traversal, URLs with credentials, and arbitrary command strings. Start uses direct process execution with `shell=False` and no manifest-controlled arguments.

Power On verifies package hash, executable hash, Basic compatibility, publisher trust, and lifecycle identity before spawn. It then requires a signed mutual-authentication handshake and a signed healthy `READY` response. A live PID alone never activates module categories.

Power Off first requests signed graceful shutdown. A forced fallback is allowed only against the exact child handle Basic created in the current process. Restart is one bounded stop/start cycle. The crash counter tracks **consecutive** failures only: a healthy authenticated `READY` (during start, health checks, or reconciliation) resets it to zero, while three consecutive failures quarantine the module; there is no infinite restart loop.

## Runtime reconciliation after a Basic restart

In-flight lifecycle states (`STARTING`, `AUTHENTICATING`, `STOPPING`) can never be trusted again after a Basic restart and are forced to `ERROR`. Runtimes that had reached `READY`/`BUSY` may survive the host restart; Basic re-adopts them only after every check below passes, never merely because a process listens on the pinned loopback URL:

1. pinned module identity — the stored manifest signature verifies under the stored module public key;
2. package integrity — the signed package SHA-256 still matches the package on disk;
3. expected executable identity — the signed lifecycle executable hash still matches the file on disk;
4. protocol compatibility — the manifest still supports this Basic version;
5. signed challenge — a mutually-authenticated handshake plus health check against the exact pinned base URL (no port scan).

Any failure is fail-closed and leaves the module in `ERROR`; three consecutive reconciliation failures quarantine it. See `RuntimeSupervisor.reconcile_existing_runtime` and the startup hook in `backend/app/main.py`.

## Capability APIs

Authenticated modules may use only the narrow `/system-link/module-api/v1` surface and only while `READY`/`BUSY`:

- `GET /cases/{case_id}` requires `case.read`;
- `GET /cases/{case_id}/evidence` requires `evidence.read` and omits managed filesystem paths;
- `POST /status` requires `module.status.publish`.

There is no raw SQLite, arbitrary filesystem, shell, secret, Tauri-state, or cross-module API.

## Navigation and isolated module UI

Core routes remain a closed TypeScript union. Dynamic routes use the validated namespace `module:<module-id>:<category-id>`, are created only from the persisted verified manifest, and enter navigation only while the module is enabled, capability-granted, and authenticated `READY`/`BUSY`. Unknown hashes and core-route collision attempts fall back safely.

Verified module package files are served through the single host route `GET /system-link/modules/{module_id}/ui/{path}` with path-containment validation, an allow-listed MIME set, a strict CSP (`default-src 'none'`, `script-src 'self'`, `connect-src 'none'`, `frame-ancestors 'self'`), `nosniff`, `no-referrer`, and `same-origin` resource policy. The frontend renders that surface inside a sandboxed iframe without `allow-same-origin` (opaque origin — the module can never read Basic cookies, tokens or storage). The only communication channel is a versioned `postMessage` bridge (`frontend/src/system-link/moduleSurface.ts`) gated by a per-surface nonce and an operation allow-list:

- `case.read`, `evidence.read` are the only data operations currently exposed;
- every operation is capability-checked again on the host backend;
- messages are validated at runtime, bounded, and reject unknown operations/namespaces;
- the module is always identified by its namespace, and the bridge closes on any validation failure.

The OIHK System Link control plane displays the Evidence Lab product card even when it is not installed or is linked-off. It exposes pairing, grant approval, Power On, Power Off, Restart, disable/enable, revoke, diagnostics, and bounded cancellation according to current state.

## End-to-end verification

`scripts/smoke_system_link_e2e.py` is the authoritative real E2E between the two products (no mocks). Against a local `OiHK-evidence-lab` clone it builds the runtime executable, builds the module UI, signs the package with a DEVELOPMENT publisher identity, starts a real Basic backend, and verifies: pair/start, signed pairing proof, capability approval, Power On, real runtime spawn, Ed25519 mutual authentication, health `READY`, authorized case and evidence queries, status publish, Power Off, Restart, replay rejection, package tampering rejection, and executable tampering rejection. Every temporary process and directory is cleaned up even on failure:

```bash
python scripts/smoke_system_link_e2e.py --evidence-lab /path/to/OiHK-evidence-lab
```
