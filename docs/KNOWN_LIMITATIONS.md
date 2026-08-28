# OIHK Basic — Known Limitations

These are intentional product boundaries or explicit adapter gaps, not simulated features.

## Analysis and OSINT

- DNS, RDAP/WHOIS and certificate transparency are the built-in network lookups.
- Lookup inputs must be syntactically valid hostnames or IPv4 literals. Values that are not — including anything carrying a URL delimiter — are refused rather than escaped, so a transform run against a malformed entity value returns no results instead of contacting the network.
- Third-party lookup responses are read under a size ceiling (`OIHK_MAX_LOOKUP_RESPONSE_BYTES`, default 5 MB). A registry returning more than that yields a partial-lookup error rather than a complete result; certificate-transparency queries for very large domains can hit this.
- Username, phone, generic text, crypto address and remote hash intelligence require a legitimate user-configured adapter; Basic reports the adapter gap instead of inventing results.
- Cross-case correlation uses deterministic attribute overlap; it is not an identity-resolution engine.

## Models

- No model weights or inference server are bundled.
- Copilot and assisted report drafts require a local or private compatible endpoint configured by the user. LM Studio is the currently validated backend; Ollama and other OpenAI-compatible endpoints exist in code but are not guaranteed in this preview.
- Model output is unverified and cannot approve or mutate evidence automatically.
- The Agent can invoke application operations by name, and eight of them write: creating or updating an investigation, adding a graph entity or relationship, running an OSINT lookup, promoting an OSINT result, generating a report, and running a transform. Writes are additionally gated on a keyword match against your own message, which bounds an over-eager model but does not understand negation and is not a security boundary. Every write is audited under your name; review the audit trail rather than assuming a write was requested.
- Model responses are bounded (`OIHK_MAX_MODEL_RESPONSE_BYTES`, default 8 MB) and streamed completions stop at `OIHK_MAX_MODEL_STREAM_CHARS` (default 1,000,000 characters). A long generation is truncated at that ceiling rather than allowed to run unbounded.

## Evidence and reports

- Basic does not acquire or analyse evidence. It keeps the custody register — what the installation holds, who put it there, and whether a held file still matches its seal — while acquisition, hashing, carving and analysis belong to OIHK Evidence Lab, installed separately and linked through System Link. With no module linked, a case can hold no new evidence.
- There is no in-app preview of an exhibit's contents. Rendering an exhibit is the linked module's surface, which Basic hosts in a sandboxed frame rather than parsing itself.
- An exhibit recorded by reference (`evidence.import`) has no bytes in managed storage, so Basic cannot re-hash it. Verification is refused for those rather than answered with a mismatch that would read as tampering.
- Reports export Markdown, safe HTML and structured JSON. PDF and DOCX renderers are not bundled.
- Graph PNG export is available from the graph workspace but is not embedded automatically in report documents.
- A storage-directory change requires backup and restart; live database relocation is deliberately blocked.

## Desktop distribution

- Windows NSIS packaging is implemented for x64. Every release candidate still requires installation, upgrade and uninstall validation on a clean Windows VM.
- macOS releases require an Apple Developer identity for signing and notarization.
- Windows executables may need code signing to avoid SmartScreen reputation warnings.
- The signed Tauri updater is implemented but has never served a client, because no release has been published yet. The repository is public, so anonymous reachability is no longer what blocks it; what remains is a signed release built with the production keys, which are deliberately not stored here. Until one exists there is nothing for the `alpha`, `beta` or `stable` channel metadata to point at, and the promotion workflow refuses to run without a published non-draft `basic-v*` tag.
- A valid end-to-end updater test requires the protected production/test signing key and a controlled public HTTPS endpoint; neither is stored in this repository.
- Cancellation during an active updater HTTP transfer is best-effort, although cancellation prevents installation.
- Linux and macOS builders exist, but the current readiness review targets Windows x64 and does not declare those artifacts release-ready.

## Local API access

- The backend answers only on loopback authorities. A request whose `Host` header names anything else is refused, which is what stops a DNS-rebinding page — but it also means a custom deployment reached under a real hostname must list it in `OIHK_ALLOWED_HOSTS`.
- Cross-origin state changes are refused against the `OIHK_CORS_ORIGINS` allowlist. A separately hosted frontend, or a dev server on an unlisted port, must be added there or its writes will fail with `origin_not_allowed`.
- Interactive API docs are unavailable in the packaged desktop build. Use a development run, or set `OIHK_DOCS_ENABLED=true`.
- Responses are sent with `Cache-Control: no-store`, so evidence previews and other assets are re-fetched rather than cached by the webview.

## Edition boundary

Basic does not include teams, organizations, enterprise SSO, cloud synchronization, private connector administration, billing, licensing, Redis, queues, GraphQL or distributed infrastructure.
