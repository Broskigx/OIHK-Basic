# Threat Model

_Last updated: 2026-07-31 · Applies to OIHK Basic v0.1.x_

This document describes the trust boundaries, assets, threat actors and
mitigations relevant to OIHK Basic. It is intended to help reviewers and
deployers reason about the security posture of the application.

## 1. Trust boundaries

```
┌────────────────────────────── Desktop device ─────────────────────────────┐
│                                                                            │
│  Tauri webview (frontend)  ── IPC (capability-scoped) ──> Rust core        │
│       │                                                                     │
│       │  localhost HTTP (JWT/CSRF when auth enabled)                        │
│       ▼                                                                     │
│  FastAPI backend (sidecar)  ── SQLite (local file, OS app-data dir)        │
│       │                                                                     │
│       ├── local model endpoint (localhost / private / link-local)          │
│       └── OSINT adapters (public services, only on explicit user action)   │
└────────────────────────────────────────────────────────────────────────────┘
```

- **Boundary A — Tauri IPC:** the webview talks to the Rust core only through
  declared capabilities. The shell plugin, arbitrary filesystem access and
  arbitrary command execution are **not** exposed.
- **Boundary B — backend HTTP:** by default the backend listens on loopback
  with authentication disabled for single-user desktop use. Exposing it
  beyond loopback is unsupported unless authentication is enabled with a
  configured administrator and strong secrets; production mode refuses to
  start otherwise.
- **Boundary C — local model endpoints:** endpoints must be localhost,
  private-network or link-local addresses. Public endpoints and embedded
  credentials are rejected.
- **Boundary D — OSINT adapters:** outbound requests only happen after an
  explicit user action, never in the background.
- **Boundary E — OIHK System Link:** separately installed first-party modules
  pair with Ed25519 installation identities. Lifecycle is restricted to a
  signed, hashed installer record and module APIs require capabilities plus
  signed timestamped nonces with replay rejection.

## 2. Assets

| Asset | Where | Primary threat |
| --- | --- | --- |
| Case/investigation data | SQLite, managed storage | Loss, tampering, exfiltration |
| Evidence files | Managed storage (SHA-256 hashed) | Tampering, path traversal, malware |
| Conversations | SQLite | Loss, model exfiltration |
| Graph entities/relations | SQLite | Tampering |
| Model credentials | Local config | Theft |
| Report HTML | Generated with escaping + CSP | XSS |
| Updater artifacts | Signed over HTTPS | Supply-chain |

## 3. Threat actors

1. **Casual local user** of the same OS account — low sophistication.
2. **Malicious local process** running as the same user (malware on the host).
3. **Network adversary** — only relevant if the backend or webview is exposed.
4. **Malicious model output** — a local model returning crafted prompts.
5. **Supply-chain attacker** — a compromised release channel or dependency.

## 4. Threats and mitigations

### T4.1 Remote code execution via the webview
The Tauri webview exposes only core capabilities and a narrow set of
commands (managed-backend lifecycle/status and opening the fixed backup
directory). No shell plugin, no arbitrary fs access, no arbitrary command
execution. A restrictive CSP constrains scripts, objects, base URLs,
connections and images.

### T4.2 Model output executing commands or exfiltrating data
Generated text is treated as **data, never as instructions**. Prompts require
evidence-backed answers without invented sources. Sensitive actions require
explicit user confirmation and always show exactly what will run. Model
output is labeled unverified and must be promoted manually into a graph.

### T4.3 Path traversal / arbitrary file access
Evidence uploads are streamed, size-limited, sanitized, copied atomically
below managed storage and hashed. Paths are resolved against the managed
root; escape attempts fail closed. Preview is inline only for safe raster
image MIME types; SVG and other files download as attachments with
`nosniff`.

### T4.4 XSS via reports and markdown
Report HTML is escaped (`html.escape`), sandboxed and served with a
restrictive CSP. No raw HTML from untrusted sources is executed in the app
context.

### T4.5 SSRF via model endpoints or OSINT
Model endpoints must be loopback/private/link-local. Public endpoints and
URL-embedded credentials are rejected. OSINT adapters target fixed,
allow-listed services and only on user action.

### T4.6 SQL injection
All database access goes through SQLAlchemy Core/ORM parameter binding.
No user input is string-interpolated into SQL.

### T4.7 Local data theft (malware on host)
Defense in depth: no secrets are compiled into the binary or committed to
the repository; secrets are generated atomically in the OS config directory;
logs/diagnostics/backups redact secrets and credentials; backups exclude
sensitive material.

### T4.8 Supply chain: unsigned or replayed updates
Updates require a Tauri Minisign signature embedded in metadata served over
HTTPS. The production private key exists only in CI secrets. A verified
SQLite backup and a one-use loopback shutdown token are mandatory before
installation. Invalid signatures, failed backups, active writes and failed
sidecar shutdowns fail closed. Release workflows pin third-party actions to
immutable commits and run Gitleaks and dependency audits.

### T4.9 Archive / compressed-file extraction attacks
OOXML text extraction reads only specific named members in memory
(`word/document.xml`, `xl/sharedStrings.xml`) and never extracts archives to
disk, so there is no path-traversal surface. Evidence uploads are streamed
and size-limited before any parsing.

> **Known gap:** there are no explicit per-entry decompression size limits yet.
> A crafted archive with a high compression ratio could inflate in memory
> within the upload size limit. Recommended hardening for a future release:
> cap decompressed bytes per member.

### T4.10 Malicious or replaced System Link module
Basic rejects unknown module ids, manifest/schema/protocol incompatibility,
path traversal, symlinks, forbidden capabilities, package hash mismatch and a
changed runtime executable hash. It starts no shell/interpreter/script and
activates navigation only after signed handshake plus healthy READY. Module
requests never receive raw database/filesystem handles and replayed nonces fail.

The remaining supply-chain gap is a production Evidence Lab publisher trust
anchor and rotation policy. Current pairing proves the approved local module
identity and subsequent package continuity; it does not yet validate a vendor
certificate chain.

## 5. Residual risks

- A hostile process with the same OS account can, in principle, read
  application files at rest. Full-disk encryption is the recommended
  countermeasure for high-sensitivity investigations.
- The local model endpoint is trusted by configuration. Users should point
  it at software they control (LM Studio, Ollama, etc.).
- Network deployments require careful secret management and are only
  supported with authentication enabled.

## 6. Security fixes

See [SECURITY.md](SECURITY.md) for the supported-version policy and
responsible disclosure process.
