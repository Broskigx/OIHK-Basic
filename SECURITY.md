# Security Policy

## Supported version

Security fixes target the current `0.2.x` beta line until a newer release policy is published.

## Local trust boundary

OIHK Basic is a single-user desktop application. Authentication is disabled by default and the backend is therefore restricted to loopback. Do not expose that mode through port forwarding, a reverse proxy or a non-loopback bind. Custom network deployments must enable authentication and configure an administrator and strong environment-specific secrets.

Loopback bounds the *network*, not the *browser*. A web page the operator visits can issue requests to 127.0.0.1, so two controls apply on every request regardless of the authentication mode:

- **Host validation.** The `Host` authority is checked on every method, reads included. A loopback bind accepts only loopback authorities, which is what refuses a DNS-rebinding answer that points an attacker-controlled name at the local port. Non-loopback deployments must list their hostnames in `OIHK_ALLOWED_HOSTS`; in production the server refuses to start without them rather than failing open.
- **Origin validation.** Unsafe methods are checked against the origin allowlist before routing and before body parsing. This exists because CORS does not stop cross-origin *writes*: the ingestion routes accept `multipart/form-data`, a CORS-safelisted content type that is never preflighted, so a hostile page could otherwise plant a file in a case and simply not read the reply. Requests with no `Origin` are ordinary non-browser callers and pass; a browser reporting `Sec-Fetch-Site: cross-site` is refused even without one.

Interactive API documentation (`/docs`, `/redoc`, `/openapi.json`) is served in development only. The packaged desktop build and production withdraw it, since it maps the API for anyone who does reach the port. Set `OIHK_DOCS_ENABLED=true` to override.

Every response carries `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `Cross-Origin-Opener-Policy: same-origin`, a restrictive `Permissions-Policy`, `Cache-Control: no-store` and `X-Frame-Options: DENY`. A route that sets one of these itself keeps its own value, so the evidence preview sandbox and the System Link module surface remain the authority on their own content. `no-store` is deliberate: a response body here can be evidence, and the webview cache would be an unmanaged copy of it that no custody record accounts for.

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

These are known and accepted for the current beta; they are not claims of completeness.

- **Loopback is the boundary.** With authentication disabled, any local process running as the same user can reach the API. Basic refuses to start on a non-loopback bind in that mode, but it does not attempt to authenticate local callers. The `Host` and `Origin` controls bound what a *browser* can be made to do; a native process on the same account can set any header it likes and is out of their reach.
- **Session tokens are validated, not revocable.** With authentication enabled, a token is checked for signature, declared algorithm, issuer and expiry, and the account must still be active. There is no server-side revocation list, so a leaked token stays usable until it expires.
- **Third-party lookup content is not verified.** Bounding a response prevents resource exhaustion; it does not make RDAP, crt.sh or model output trustworthy. Findings remain unpromoted until a user acts on them.
- **DNS rebinding on model endpoints is mitigated, not eliminated.** The connected peer is checked when the transport exposes it. A transport that does not expose the peer address falls back to the endpoint-string check alone.
- **Rate limiting is in-process and best-effort.** It bounds its own memory, but it is not a substitute for a network control in a shared deployment.
- **Import ceilings are fixed, not adaptive.** CSV and hash-set imports stop at a row limit rather than sizing to available resources.
- **Sidecar resolution is path-pinned, not signature-verified.** The packaged backend is loaded from the installation directory; it is not hash-checked before launch the way System Link module executables are.
- **`backend/tests` entered lint coverage in a recent pass.** It had never been linted, so previously unreported issues in that tree may still surface.
- **The backend port is chosen by probe, not reserved.** The probe listener must be released before the sidecar can bind, so a local process could take the port in between. The desktop core detects this by watching its own child while polling `/health` and refusing a reply once that child has exited, rather than adopting whatever answers on the port. The race itself is not eliminated.

## Reporting a vulnerability

Open a private security advisory in the GitHub repository. Include the affected version, reproduction steps, impact and any proposed mitigation. Do not attach real investigation data, secrets or evidence files.
