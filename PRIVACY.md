# Privacy Policy

_Last updated: 2026-07-31 · Applies to OIHK Basic v0.1.x_

OIHK Basic is a **local-first** single-user desktop application designed for
authorized investigations and lawful analysis. This policy describes what
data is collected, where it stays, and when it leaves your computer.

## 1. Data residency

- All application data — cases, investigations, conversations, graph entities,
  evidence, reports, settings and model configuration — is stored **on your
  device** in the operating-system application-data directory (or a directory
  you explicitly configure). Nothing is written to a cloud account.
- Evidence uploads are copied into managed storage under that directory.
  Original files are never silently overwritten; uploads are streamed,
  size-limited, sanitized and stored atomically.
- The local backend binds to **loopback only** by default. It is not exposed
  to your local network or the internet unless you explicitly change the
  binding, which additionally requires enabling authentication.

## 2. Local AI models

- Copilot and AI report drafting use **local inference endpoints** (for
  example LM Studio or Ollama) on `localhost`, a private network or a
  link-local address. Credentials embedded in URLs and public endpoints are
  rejected.
- Conversation content is sent only to the local model endpoint you have
  configured. It is **never** sent to a cloud AI provider.
- OIHK Basic ships with **no built-in API keys**. Any key you enter is stored
  in your local configuration and is only used to talk to the local endpoint.
- Model output is generated locally and is labeled as unverified. It is not
  inserted into a graph as fact until you explicitly promote it.

## 3. OSINT and public services

- OSINT adapters contact public services **only after an explicit user
  action** (a query you initiate). Results are stored as query history on
  your device and are **not** inserted into the graph until you promote them.
- No telemetry, crash reporting, analytics or usage statistics are collected
  or transmitted. OIHK Basic does not phone home.

## 4. Updates

- Update checks contact the configured release endpoint (GitHub releases over
  HTTPS) only when you use the updater. Update manifests must be signed with
  the public Minisign key embedded in the build; invalid signatures fail
  closed. Before installation the updater makes a verified SQLite backup and
  shuts the local backend down gracefully.

## 5. Logs, backups and diagnostics

- Logs are written locally with **rotation**. Logs, backups and diagnostics
  **redact secrets and model credentials** before export.
- The diagnostic export is generated on demand by you and contains no API
  keys, tokens or personal investigation data.

## 6. Your controls

- Delete a case, conversation or evidence item from the UI to remove it from
  the managed storage.
- Uninstallers warn before removing investigation data. See
  `docs/WINDOWS_INSTALL.md` for details.
- You can opt out of automatic update checks at any time in Settings.

## 7. Contact

Privacy and data-handling questions: open an issue on the repository or use
the process described in [SECURITY.md](SECURITY.md).
