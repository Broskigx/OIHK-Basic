# Changelog

## Unreleased

Evidence Lab left this repository. What remains is the case spine — the graph,
the sources, the reports and the custody chain — with acquisition and analysis
now belonging to a separately installed module that reaches those records
through System Link.

### Changed

- **Forensic acquisition and analysis moved to OIHK Evidence Lab.** The
  analysis engine, its routers and the workspaces that drove them are gone
  from Basic. The four evidence and custody tables are untouched — there is no
  destructive migration — because those records are exactly what the linked
  module reads and writes. `custody.seal_source` stays too: the graph, targets
  and OSINT promotion all use it, so it was never Evidence Lab's to take.
- **Ingestion and annotation left the browser API.** They arrive through the
  signed module API instead, where every write is attributed to the module
  that sent it. A second, unattributed way in would have defeated the reason
  that API is signed, so `POST /evidence` now returns 404 and a test says so.

### Fixed

- **A granted System Link capability did nothing.** The protocol declared
  fifteen and four had an endpoint behind them, so approving `evidence.write`
  for a module recorded a grant against a route that did not exist. All
  fifteen are enforced now, and a test reads the list out of the source and
  fails if one is ever declared without a route.
- **The module UI bridge ignored the module's own grants.** It validated
  message shape, per-surface nonce and event source, then served the operation
  by calling Basic's API with the *operator's* session — so the server saw an
  authorised human and enforced what that human could read, never what the
  module was approved for. A module granted navigation alone could read every
  case and every exhibit in the installation.
- **Pairing refused every module but one.** It matched a hard-coded id,
  product name and entrypoint, which made "System Link links separately
  installed OIHK modules" true of exactly one module — and stopped nobody,
  since anyone able to forge the publisher signature could also write that
  name into a manifest. The signature is the control.
- **A JPEG could dictate false dimensions to a forensic report.** Dimensions
  came from scanning the file for `FF C0`, which misses progressive JPEGs
  entirely and accepts those bytes wherever they appear — including inside an
  earlier segment's payload. Nine further defects in the same package were
  fixed before it left: RIFF resolving to `video/avi` for WAV and WebP, MP4
  matched by one encoder's box length, a global IOC ceiling that let 200
  emails starve every hash and CVE in the same document, `.pptx` returning
  empty text *and* an empty error list, and `FileAnalysis.discrepancies` being
  wired through the panel, the report and the schema while always being handed
  an empty list — so an executable named `.jpg` analysed clean.
- **A failed integrity check disappeared on reload.** `verified_at` recorded
  when an exhibit was last checked and nothing about the outcome, so a
  tampered file and an intact one were indistinguishable the moment the page
  refreshed. Migration 9 records the verdict, nullable so rows checked under
  the old schema report "no verdict on record" rather than an invented pass.
- **The System Link E2E smoke reported success without running.** It re-runs
  itself under a venv holding both products, and did that with `os.execv` —
  correct on POSIX, and on Windows a spawn-and-terminate that returned 0 to
  the caller immediately while the smoke was still building. A failing run
  exited 0 in under a second. It also dropped `--port` when relaunching, so
  the documented flag silently ran on a random port.

### Added

- **Custody register.** The verify, delete and manifest routes survived the
  split and stayed tested, but nothing called them: with no module linked an
  operator could not see what the installation held. The register lists it,
  distinguishes files Basic holds from ones it only references, re-hashes
  against the seal, exports the manifest, and removes an exhibit.
- **The E2E smoke runs in CI**, building the real Evidence Lab runtime and
  package and driving the full eighteen-step lifecycle against a real Basic
  backend. It needs the `EVIDENCE_LAB_TOKEN` secret because the module
  repository is private; without it the job explains how to create one and
  stops rather than failing.

### Security

- `pip` moved past PYSEC-2026-3721 in the locked dependency set.

## 0.2.0-beta.1 — 2026-08-14

First beta candidate. This release is about correctness and evidence rather than features: the loopback API gained the browser-facing controls it was missing, the REST surface gained an integration suite that immediately found real defects, and the coverage tooling that was supposed to measure all of it turned out to be misreporting.

### Fixed

- **A case holding managed evidence could not be deleted at all.** `evidence_items` and `evidence_seals` reference `sources` with `ondelete=RESTRICT`, and deleting a case cascades to its sources, so SQLite refused the whole transaction and the route returned a server error. Those tables are now cleared first, and the managed files they point at are unlinked after the transaction commits — a deleted case no longer leaves orphaned evidence on disk either.
- **The System Link module surface read a file whole before deciding it was too large.** The comment above it described a bounded read loop, and the code was a `read_bytes()` followed by a length check — so the 16 MB ceiling was a report on an allocation that had already happened rather than a control preventing it. The read is now chunked, refuses inside the loop, and runs on a worker thread instead of blocking the event loop for the length of a large file.
- **A case with no `organization_id` was reachable by id but absent from every listing.** The listing filter compared the column directly, and in SQL a NULL equals nothing; the per-case check read the same NULL as `"default"` and granted access. The two now normalise a missing organization the same way, so a record that can be opened can also be found.
- The rate limiter compared its key ceiling with `>` when sweeping and `>=` when refusing, leaving one value — the ceiling itself — where no sweep ran and an unknown client was rejected anyway on entries the sweep would have released.
- Graph entity creation recorded the audit actor as a hardcoded `"analyst"` instead of the acting user, unlike every other audited action.
- The refusal to rotate signing keys checked for a database at the platform default path rather than the one the process was told to open, so the guard stopped protecting a relocated data directory. `verify_password` also raised instead of returning `False` when the algorithm or round count in a stored record could not be read.
- A startup that correctly refused to mint new keys reached the operator as a traceback, and through the desktop shell as nothing but "the backend exited". The refusal now prints what happened and what to do about it.
- Legacy evidence storage named files by content digest, so two ingestions of the same bytes under the same name collided on one path and deleting either record unlinked the file the other still pointed at. It now names files the way managed evidence already did.
- A relationship label of pure whitespace satisfied the schema's `min_length` and then normalised to nothing, so an edit could empty a predicate that creation would have refused.
- Restoring a graph snapshot re-seeded workspace positions for entities deleted since it was taken; it now drops unknown ids the same way saving a workspace does.

### Added

- `Host` header validation on every request. A loopback bind accepts only loopback authorities, which is what refuses a DNS-rebinding answer aimed at the local port. Non-loopback deployments declare their names in `OIHK_ALLOWED_HOSTS`, and production refuses to start without them.
- `Origin` and `Sec-Fetch-Site` validation on state-changing requests, applied independently of the authentication mode. CORS never blocked cross-origin *writes*: the ingestion routes accept `multipart/form-data`, which is not preflighted, so a hostile page could plant a file in a case and simply not read the reply.
- Baseline response headers on every route — `nosniff`, `Referrer-Policy`, `Cross-Origin-Opener-Policy`, `Permissions-Policy`, `Cache-Control: no-store`, `X-Frame-Options` — never overwriting a header a route set for its own content.
- An HTTP-level integration suite covering cases, evidence, the graph, reports, settings, dashboard, custody, exports and operations. The suite grew from 191 to 326 tests.
- Snapshot retention: a case keeps the newest 100, matching the number the list route returns. Writes were previously unbounded behind a capped read, so anything past the ceiling accumulated invisibly.
- Explicit claim validation on session tokens (declared algorithm, issuer, expiry) and boot-time refusal tests for every unsafe configuration.

### Changed

- Interactive API docs are withdrawn from the packaged desktop build and from production; `OIHK_DOCS_ENABLED` overrides.
- CORS methods and headers are enumerated rather than wildcarded.
- The test suite runs in about two minutes despite carrying 76 more tests, by building the schema once per session instead of per test.
- CI enforces a coverage floor as part of the existing test step rather than as a second pass.

### Removed

- `app/investigation/` and `app/services/memory_store.py`. Both were unreachable, and the former shipped a second `InvestigationNode`/`InvestigationEdge` type system and a duplicate correlation implementation competing with `services/analyzer.py` and `services/correlation.py` — while being bundled into the desktop binary by a PyInstaller hidden import.

### Quality

- **Coverage was being measured wrongly.** SQLAlchemy's asyncio layer switches greenlets, and without declaring that concurrency the tracer lost the frame after every `await session.execute(...)`, reporting the following line as unexecuted. Declaring it moved the case router from a reported 38% to 91% without a single test changing; every route in the application was affected.
- A DNS-timeout test left a worker thread sleeping for thirty seconds that the executor joined at shutdown, costing that much on every run. The thread is now released once the assertion it supports has passed.
- A root `ruff.toml` extends the backend configuration so lint from the repository root, from an editor and in CI produce the same result. Previously a root run lost `known-first-party` and reported import-order errors CI considered clean.

## 0.1.1-alpha.2 — 2026-07-31

Second alpha candidate for testers: streaming Copilot, per-conversation model settings, a faster Canvas layout engine and a clear split between local unsigned builds and signed alpha releases.

### Added

- Server-Sent-Events (SSE) streaming for Copilot replies with incremental deltas, bounded retries and no lost user turns on disconnect.
- Per-conversation model and settings persistence (schema migration 4) so each chat remembers the model it was drafted with.
- Packed numeric spatial-grid keys in the Canvas layout engine: bijective cell packing, canonical cell-pair iteration and no per-tick string-keyed deduplication. Small graphs keep exact all-pairs repulsion.
- Graph performance regression tests for small, medium and large graphs (50/500/2500 nodes) plus spatial hit-test and fit-to-view coverage.
- `npm run check`, `npm run tauri:build`, `npm run release:local` (unsigned, no updater, no signing keys) and `npm run release:alpha` (signed updater), with `src-tauri/tauri.local.conf.json` keeping local builds updater-free.
- `PRIVACY.md`, `THREAT_MODEL.md` and `RESPONSIBLE_USE.md`, plus `OIHK_AUDIT.md` and `backend/.env.example`.
- Database migration runner now skips `ALTER TABLE ADD COLUMN` statements whose columns already exist on fresh databases.

### Security

- Copilot still talks only to loopback/private endpoints; streaming does not change the local-model trust boundary.
- Local unsigned builds cannot silently degrade into signed releases: missing signing keys fail the build with a clear message.

### Quality

- Version metadata synchronized to 0.1.1-alpha.2 across every build surface.
- Documentation aligned on Node.js 22 (matching `frontend/package.json` engines) and the current alpha/testing status.

## 0.1.1-alpha.1 — 2026-07-28

First public-alpha candidate for the standalone OIHK Basic desktop application.

### Added

- Separate local-first single-user repository, data directory and desktop runtime.
- Eleven complete product workspaces and eight-step optional onboarding.
- Premium Canvas 2D graph with persistent positions/camera, minimap, layouts, filters, multi-select, pinning, undo/redo and named snapshots.
- Full investigation lifecycle with versioned JSON portability.
- Explicit OSINT history and promotion workflow without automatic graph mutation.
- Managed evidence streaming, SHA-256 verification, provenance, manifest export and safe previews.
- Persistent report documents/templates with Markdown, sandboxed HTML, JSON and optional local-model drafts.
- Persistent Copilot conversations using only LM Studio, Ollama or private compatible endpoints.
- Versioned application settings, storage diagnostics and SQLite backups.
- Tauri 2 packaging with a bundled PyInstaller backend and Windows NSIS installer.
- Official Tauri 2 signed updater with explicit download/restart decisions, progress, release notes, safe deferral and alpha/beta/stable channel metadata.
- Mandatory pre-update SQLite checkpoint, verified online backup, SHA-256 metadata, write draining and one-use graceful sidecar shutdown.
- Formal checksum-protected `schema_migrations` history, migration backups and recovery status surfaced in Settings/About.
- Pinned CI/release workflows that gate draft prereleases on tests, lint, dependency audits, Gitleaks, PyInstaller smoke and artifact validation.

### Security

- Loopback enforcement for the default no-login desktop mode.
- Atomic first-run secrets and managed file writes.
- Private/local model endpoint validation and credential rejection in URLs.
- Restrictive webview/report CSP, safe error rendering and no exposed shell plugin.
- Bounded uploads/reads, path confinement, attachment-only unsafe previews and evidence hash re-verification.
- Updater private keys remain CI-only; invalid or absent signatures and incomplete artifacts fail closed.
- Public URL ingestion rejects credentials, private/local/reserved destinations, onion hosts and unsafe redirect hops while enforcing streamed response limits.
- Chain-of-custody verification rehashes managed evidence files and checks the per-case anchor for truncation.
- Packaged sidecars ignore working-directory `.env` files, use a fixed application-data working directory and exit if their Tauri parent disappears.
- Spreadsheet exports neutralize user-controlled formula cells, CSRF works in optional-auth mode, and OOXML extraction is bounded against decompression bombs.

### Quality

- Backend, frontend, graph performance, portability, packaging and installed-sidecar regression coverage.
- Correct direct hash routing for case workspaces.
- Adaptive spatial force layout for large graphs.
- Linear-time forensic entropy calculation with regression coverage for binary uploads.
