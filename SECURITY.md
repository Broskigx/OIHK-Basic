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

Copilot and AI report drafts require an endpoint on localhost, a private network or link-local address. Credentials embedded in URLs and public endpoints are rejected. Model output is labeled as unverified and prompts require evidence-backed answers without invented sources.

OSINT adapters can contact public services only after a user action. Results are stored as query history and are not inserted into the graph until explicit promotion.

## Desktop hardening

The Tauri webview exposes core capabilities, the official updater default capability, and narrow commands for managed-backend lifecycle/status and opening the fixed backup directory. It does not expose the shell plugin, arbitrary filesystem access or arbitrary command execution. CSP restricts scripts, objects, base URLs, connections and images. The packaged backend is started with loopback and authentication-disabled desktop settings.

Updates require a Tauri Minisign signature embedded in metadata served over HTTPS. The production private key is accepted only through CI secrets. A verified SQLite backup and one-use loopback shutdown token are mandatory before installation. Invalid signatures, failed backups, active writes and failed sidecar shutdowns fail closed.

Release workflows pin third-party actions to immutable commits, run Gitleaks and dependency audits, and create draft prereleases only. See [docs/UPDATES.md](docs/UPDATES.md) for recovery and [docs/RELEASING.md](docs/RELEASING.md) for key custody and rotation.

## Reporting a vulnerability

Open a private security advisory in the GitHub repository. Include the affected version, reproduction steps, impact and any proposed mitigation. Do not attach real investigation data, secrets or evidence files.
