# Threat Model

_Last updated: 2026-08-14 · Applies to OIHK Basic v0.2.x_

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
  start otherwise. Loopback is a boundary against the *network*, not against
  the *browser*: a page the operator visits can reach 127.0.0.1, so the
  `Host` and `Origin` controls in T4.11 and T4.12 apply regardless of the
  authentication mode.
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
The local Agent selects operations by name from a fixed allowlist
(`app/services/assistant_tools.py`). The model never reaches the database, the
filesystem or the network itself: it emits a JSON envelope naming a tool, and
the corresponding application route runs it as the real authenticated user, so
every access-control rule is inherited rather than reimplemented. The allowlist
deliberately excludes evidence mutation, deletion of anything, report approval,
settings and System Link control — the model can draft, it cannot destroy or
attest.

**Injected instructions inside investigation data.** Sources, OSINT answers and
ingested pages are third-party text and must be assumed hostile. The property
that contains them is structural: a turn is one model call, at most four tool
calls, and tool *results are never fed back to the model* — the reply the user
sees is assembled deterministically from the tool summaries. Nothing an
attacker writes into a page or a registry response re-enters the model's
context through this path, so it cannot steer a following call.

**The write gate is not a security control.** Mutating tools additionally
require a keyword match against the user's own message. That bounds an
over-eager model; it is not a boundary. It does not understand negation, and
its patterns share ordinary verbs, so an innocuous message can satisfy one. It
fails closed for a tool with no registered pattern.

Residual: the model chooses the *arguments*. A wrong or manipulated call inside
the allowlist can create an investigation, add a graph entity or relationship,
run an OSINT lookup, or generate a draft report. Every such write goes through
the audited route and is recorded against the acting user, which is what makes
it reviewable after the fact. Model output remains labeled unverified.

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
path traversal, symlinks, forbidden capabilities, package hash mismatch, a
changed runtime executable hash, and untrusted publisher identity. It starts
no shell/interpreter/script and activates navigation only after signed
handshake plus healthy READY. Module requests never receive raw
database/filesystem handles and replayed nonces fail. The single-use Link Key
is claimed with an atomic conditional update, so concurrent replays cannot
both succeed and a failed post-claim step rolls back without burning the key.

Publisher trust is implemented as an embedded first-party trust anchor set
(Ed25519). Release packages must verify under an anchor in
`RELEASE_TRUST_ANCHORS`; development packages are accepted only when the host
explicitly enables them and are tagged with the `development` channel. Invalid
signatures, unknown publishers, and altered packages or manifests fail closed
before the Link Key is consumed. Key rotation is supported by adding the
successor anchor before switching, keeping both during a transition window,
then retiring the old one.

After a Basic restart, in-flight lifecycle states are forced to ERROR. A
runtime that had reached READY/BUSY is re-adopted only after re-verifying the
pinned module identity, package hash, expected executable hash, protocol
compatibility, and a signed mutually-authenticated handshake against the
pinned loopback URL — never merely because a process listens on the port.

Non-Windows installation identities are protected by the OS keyring (macOS
Keychain / Linux Secret Service via the `keyring` package) with an explicit
AES-GCM mode-`0600` fallback only when no keyring backend exists; the active
provider is reported per installation through `key_storage`.

### T4.11 Cross-origin writes from a page the operator visits
The browser is inside the trust boundary; a web page it loads is not. CORS
was never the control that stopped a cross-origin *write*: it withholds the
response, not the request. The ingestion routes accept `multipart/form-data`,
a CORS-safelisted content type, so a plain `<form>` submission to the loopback
port is not preflighted at all — the write lands and the attacker simply never
reads the reply. For a forensics tool that is the wrong half to protect,
because planting a file in a case is itself the damage.

Every unsafe method is therefore checked against the origin allowlist before
routing, before body parsing and before any database work, and independently
of whether authentication is enabled. Requests carrying no `Origin` are the
ordinary non-browser callers (the Tauri core, the System Link smoke runner)
and pass; a browser labelling the request `Sec-Fetch-Site: cross-site` or
`same-site` is refused even if it omitted `Origin`. The System Link module API
is exempt because it authenticates each call with a signed, timestamped
envelope bound to a paired Ed25519 identity.

### T4.12 DNS rebinding against the loopback API
An origin check cannot address this one. If an attacker's domain re-resolves
to 127.0.0.1, the browser believes the page and the API share an origin: it
sends no `Origin`, reports `Sec-Fetch-Site: same-origin` and applies no CORS.
Reads succeed, which with authentication disabled means the whole case
database, evidence and conversation history.

The one header that still carries the attacker's own name is `Host`, so the
authority is validated on **every** method, reads included. A loopback bind
accepts only loopback authorities; that is derived automatically and needs no
configuration. A non-loopback deployment sits behind a proxy that rewrites
`Host` to a name only the operator knows, so it must state the expected names
in `OIHK_ALLOWED_HOSTS` — and in production the server refuses to start
without them rather than failing open. The randomly chosen backend port raises
the cost of finding the service but is not itself a control.

## 5. Residual risks

- A hostile process with the same OS account can, in principle, read
  application files at rest. Full-disk encryption is the recommended
  countermeasure for high-sensitivity investigations.
- The local model endpoint is trusted by configuration. Users should point
  it at software they control (LM Studio, Ollama, etc.).
- Network deployments require careful secret management and are only
  supported with authentication enabled.
- The browser controls in T4.11 and T4.12 bound what a *web page* can do to
  the loopback API. They do nothing against a malicious native process on the
  same account, which can set any header it likes; that case remains covered
  only by the OS account boundary.
- `Sec-Fetch-Site` is treated as corroborating evidence, never as the sole
  basis for accepting a request. A client that omits it is judged by `Origin`
  and `Host` alone.
- The System Link runtime executable is hashed and then launched by path, so a
  writer able to replace that file in between runs code the hash check
  approved. Closing the window means executing the handle that was verified,
  which the supported platforms do not offer portably. The boundary that
  actually holds here is write access to the installation directory, not the
  comparison — the same actor could rewrite the manifest and the recorded hash
  along with the binary.

## 6. Security fixes

See [SECURITY.md](SECURITY.md) for the supported-version policy and
responsible disclosure process.
