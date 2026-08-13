# Security Policy

## Supported version

Security fixes target the current `0.1.x` line until a newer release policy is published.

## Local trust boundary

OIHK Basic is a single-user desktop application. Authentication is disabled by default and the backend is therefore restricted to loopback. Do not expose that mode through port forwarding, a reverse proxy or a non-loopback bind. Custom network deployments must enable authentication and configure an administrator and strong environment-specific secrets.

## Data and evidence

- Application data stays in the operating-system application-data directory unless explicitly overridden.
- Evidence uploads are streamed, size-limited, sanitized, copied atomically below managed storage and hashed with SHA-256.
- Preview is inline only for safe raster image MIME types; SVG and other files download as attachments with `nosniff`.
- Report HTML is escaped, sandboxed and generated with a restrictive CSP.
- Backups and diagnostics omit secrets and model credentials.

## Local models and external services

Copilot and AI report drafts require an endpoint on localhost, a private network or link-local address. Credentials embedded in URLs and public endpoints are rejected. The endpoint string is validated before use, and for the hostname forms that resolve at connect time the established peer address is re-checked against the private ranges, so a rebinding answer is refused before any body is read. Model output is labeled as unverified and prompts require evidence-backed answers without invented sources.

OSINT adapters can contact public services only after a user action. Results are stored as query history and are not inserted into the graph until explicit promotion.

### Untrusted response handling

Third-party registries, certificate-transparency mirrors and operator-configured model servers are outside the trust boundary, so their responses are treated as untrusted input:

- Every outbound JSON body is read through a streaming reader with a byte ceiling applied *after* transparent content decoding, so a compressed response cannot expand without bound in memory. The ceilings are `OIHK_MAX_LOOKUP_RESPONSE_BYTES` (default 5 MB) and `OIHK_MAX_MODEL_RESPONSE_BYTES` (default 8 MB).
- Streamed completions stop at `OIHK_MAX_MODEL_STREAM_CHARS` (default 1,000,000) so an endpoint that never terminates its stream cannot accumulate without limit.
- Values taken from investigation data are validated as hostnames or IPv4 literals before being placed in a request URL. A transform validates the entity *type* against its declared inputs, but the entity *value* is free-form and is revalidated by each adapter.
- Name resolution runs in a worker thread under an explicit timeout. A blackholed hostname in investigation data therefore cannot stall the event loop.

### Untrusted rendering

Source URLs and entity labels originate in ingested pages, imported files and third-party lookups. The interface renders a link only when the value parses as `http:` or `https:`; anything else, including `javascript:` and `data:`, is rendered as inert text. External links carry `rel="noopener noreferrer"`.

## Desktop hardening

The Tauri webview exposes core capabilities, the official updater default capability, and narrow commands for managed-backend lifecycle/status and opening the fixed backup directory. It does not expose the shell plugin, arbitrary filesystem access or arbitrary command execution. CSP restricts scripts, objects, base URLs, connections and images. The packaged backend is started with loopback and authentication-disabled desktop settings.

Updates require a Tauri Minisign signature embedded in metadata served over HTTPS. The production private key is accepted only through CI secrets. A verified SQLite backup and one-use loopback shutdown token are mandatory before installation. Invalid signatures, failed backups, active writes and failed sidecar shutdowns fail closed.

Release workflows pin third-party actions to immutable commits, run Gitleaks and dependency audits, and create draft prereleases only. See [docs/UPDATES.md](docs/UPDATES.md) for recovery and [docs/RELEASING.md](docs/RELEASING.md) for key custody and rotation.

## Residual risks

These are known and accepted for the current alpha; they are not claims of completeness.

- **Loopback is the boundary.** With authentication disabled, any local process running as the same user can reach the API. Basic refuses to start on a non-loopback bind in that mode, but it does not attempt to authenticate local callers.
- **Third-party lookup content is not verified.** Bounding a response prevents resource exhaustion; it does not make RDAP, crt.sh or model output trustworthy. Findings remain unpromoted until a user acts on them.
- **DNS rebinding on model endpoints is mitigated, not eliminated.** The connected peer is checked when the transport exposes it. A transport that does not expose the peer address falls back to the endpoint-string check alone.
- **Rate limiting is in-process and best-effort.** It bounds its own memory, but it is not a substitute for a network control in a shared deployment.
- **Import ceilings are fixed, not adaptive.** CSV and hash-set imports stop at a row limit rather than sizing to available resources.
- **Sidecar resolution is path-pinned, not signature-verified.** The packaged backend is loaded from the installation directory; it is not hash-checked before launch the way System Link module executables are.
- **`backend/tests` entered lint coverage in this pass.** It had never been linted, so previously unreported issues in that tree may still surface.

## Reporting a vulnerability

Open a private security advisory in the GitHub repository. Include the affected version, reproduction steps, impact and any proposed mitigation. Do not attach real investigation data, secrets or evidence files.
