# OIHK Basic — Known Limitations

These are intentional product boundaries or explicit adapter gaps, not simulated features.

## Analysis and OSINT

- DNS, RDAP/WHOIS and certificate transparency are the built-in network lookups.
- Username, phone, generic text, crypto address and remote hash intelligence require a legitimate user-configured adapter; Basic reports the adapter gap instead of inventing results.
- YARA scanning is not bundled. Hash matching, MIME detection, metadata, IOC extraction and carving remain available.
- Cross-case correlation uses deterministic attribute overlap; it is not an identity-resolution engine.

## Models

- No model weights or inference server are bundled.
- Copilot and assisted report drafts require LM Studio, Ollama or a private compatible endpoint configured by the user.
- Model output is unverified and cannot approve or mutate evidence automatically.

## Evidence and reports

- Inline evidence preview is restricted to safe raster image types. Other files are downloaded as attachments.
- Reports export Markdown, safe HTML and structured JSON. PDF and DOCX renderers are not bundled.
- Graph PNG export is available from the graph workspace but is not embedded automatically in report documents.
- A storage-directory change requires backup and restart; live database relocation is deliberately blocked.

## Desktop distribution

- Windows NSIS packaging is verified on x64. Linux and macOS scripts require native CI/hosts for final artifact testing.
- macOS releases require an Apple Developer identity for signing and notarization.
- Windows executables may need code signing to avoid SmartScreen reputation warnings.
- An automatic updater is not included in 0.1.x; updates are installed manually and preserve the OS data directory.

## Edition boundary

Basic does not include teams, organizations, enterprise SSO, cloud synchronization, private connector administration, billing, licensing, Redis, queues, GraphQL or distributed infrastructure.
