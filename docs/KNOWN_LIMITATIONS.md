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
- Model responses are bounded (`OIHK_MAX_MODEL_RESPONSE_BYTES`, default 8 MB) and streamed completions stop at `OIHK_MAX_MODEL_STREAM_CHARS` (default 1,000,000 characters). A long generation is truncated at that ceiling rather than allowed to run unbounded.

## Evidence and reports

- Inline evidence preview is restricted to safe raster image types. Other files are downloaded as attachments.
- Reports export Markdown, safe HTML and structured JSON. PDF and DOCX renderers are not bundled.
- Graph PNG export is available from the graph workspace but is not embedded automatically in report documents.
- A storage-directory change requires backup and restart; live database relocation is deliberately blocked.

## Desktop distribution

- Windows NSIS packaging is implemented for x64. Every release candidate still requires installation, upgrade and uninstall validation on a clean Windows VM.
- macOS releases require an Apple Developer identity for signing and notarization.
- Windows executables may need code signing to avoid SmartScreen reputation warnings.
- The signed Tauri updater is implemented but cannot serve installed clients anonymously while its GitHub repository and release assets are private.
- A valid end-to-end updater test requires the protected production/test signing key and a controlled public HTTPS alpha endpoint; neither is stored in this repository.
- Cancellation during an active updater HTTP transfer is best-effort, although cancellation prevents installation.
- Linux and macOS builders exist, but this alpha readiness review targets Windows x64 and does not declare those artifacts release-ready.

## Edition boundary

Basic does not include teams, organizations, enterprise SSO, cloud synchronization, private connector administration, billing, licensing, Redis, queues, GraphQL or distributed infrastructure.
