# OIHK System Link v1 host foundation

OIHK Basic owns the local host/control plane. OIHK Evidence Lab remains a separate installation, process, repository, UI/domain implementation, and specialized data owner. There are no cross-repository source imports and Basic does not execute forensic code received from a module.

## Versioned contract

- System Link protocol: `1.0`
- Manifest schema: `1`
- Module SDK metadata version: `1`
- First approved host adapter: `oihk.evidence-lab`

The backend contract lives in `backend/app/system_link/`. The frontend registry and control surface live in `frontend/src/system-link/`.

## Trust and pairing

Basic creates an Ed25519 installation identity. Only its public key and SHA-256 fingerprint are stored in SQLite. On Windows the raw private key is protected with user-bound DPAPI; other platforms use AES-GCM wrapping plus a mode-`0600` file until native keychain providers are added.

`POST /system-link/pair/start` creates a 128-bit, five-minute OIHK Link Key and challenge. The database stores only the Link Key hash. `POST /system-link/pair/complete` consumes the key after the separately installed module proves possession of its Ed25519 private key, signs its manifest, and passes deterministic package verification. A host user must then approve a subset of the requested capabilities through `POST /system-link/pair/{id}/approve`.

The Link Key is single-use and never becomes a bearer credential. Later module-to-host calls use signed method/path/body/timestamp/nonce envelopes. Used nonces are persisted briefly and duplicate nonces fail closed.

## Registry and persistence

Schema migrations 6 and 7 add explicit tables for:

- Basic's public installation identity;
- linked modules and signed manifests;
- capability grants;
- pending/used pairing challenges;
- replay nonces;
- redacted System Link audit events.

Runtime/link states are explicit: `NOT_INSTALLED`, `UNLINKED`, `PAIRING`, `LINKED_OFF`, `STARTING`, `AUTHENTICATING`, `READY`, `BUSY`, `STOPPING`, `ERROR`, `INCOMPATIBLE`, `REVOKED`, `DISABLED`, and `QUARANTINED`.

`LINKED_OFF` preserves module identity, manifest, package reference, pairing, and capability grants. Revocation is a separate transition and requires new pairing.

## Lifecycle security

The lifecycle descriptor supports only `managed-process`. It contains an installer-registered absolute root, a relative executable identity, an exact SHA-256, a fixed loopback runtime URL, and bounded timeouts. It rejects shells, interpreters, scripts, path traversal, URLs with credentials, and arbitrary command strings. Start uses direct process execution with `shell=False` and no manifest-controlled arguments.

Power On verifies package hash, executable hash, Basic compatibility, and lifecycle identity before spawn. It then requires a signed mutual-authentication handshake and a signed healthy `READY` response. A live PID alone never activates module categories.

Power Off first requests signed graceful shutdown. A forced fallback is allowed only against the exact child handle Basic created in the current process. Restart is one bounded stop/start cycle. Three consecutive startup failures quarantine the module; there is no infinite restart loop.

## Capability APIs

Authenticated modules may use only the narrow `/system-link/module-api/v1` surface and only while `READY`/`BUSY`:

- `GET /cases/{case_id}` requires `case.read`;
- `GET /cases/{case_id}/evidence` requires `evidence.read` and omits managed filesystem paths;
- `POST /status` requires `module.status.publish`.

There is no raw SQLite, arbitrary filesystem, shell, secret, Tauri-state, or cross-module API.

## Navigation and UI

Core routes remain a closed TypeScript union. Dynamic routes use the validated namespace `module:<module-id>:<category-id>`, are created only from the persisted verified manifest, and enter navigation only while the module is enabled, capability-granted, and authenticated `READY`/`BUSY`. Unknown hashes and core-route collision attempts fall back safely.

The OIHK System Link control plane displays the Evidence Lab product card even when it is not installed or is linked-off. It exposes pairing, grant approval, Power On, Power Off, Restart, disable/enable, revoke, diagnostics, and bounded cancellation according to current state.

## Current limitations

- The repository does not yet contain an Evidence Lab release artifact/runtime, so cross-repository installer and signed-runtime interoperability must be validated with the Evidence Lab repository.
- The first-party catalog currently binds the Evidence Lab product/module/lifecycle ids, but a production publisher trust anchor/key-rotation policy is not yet embedded. Pairing proves the local module installation identity and package continuity, not an external vendor certificate chain.
- Dynamic category routing is implemented as a controlled host surface. Loading a separately packaged Evidence Lab UI through an isolated webview or restricted versioned SDK remains the next milestone; Basic deliberately does not execute the package JavaScript yet.
- Native macOS Keychain and Linux Secret Service providers remain to be implemented. The non-Windows private key is encrypted at rest with restrictive permissions, but is not hardware/user-keychain bound.
- Lifecycle ownership is exact for children started during the current backend session. A desktop-wide service identity/reconciliation adapter is still needed for robust control of a runtime that outlives or predates the Basic backend process.
