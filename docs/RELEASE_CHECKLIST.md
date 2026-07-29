# OIHK Basic — Public alpha release gates

This checklist records required evidence. A checked item must link to a CI run, test record, or retained operator log; a successful source build is not a substitute for clean-machine validation.

## Automated gates

- [ ] PR head is based on current `master` and all required checks are green.
- [ ] Gitleaks passes against the complete Git history with only exact documented placeholders allowed.
- [ ] Ruff, root/backend tests, portability tests, `pip check`, and the locked Python dependency audit pass.
- [ ] `npm ci`, ESLint, Vitest, production build, and npm audit pass.
- [ ] `cargo fmt --check`, locked default/updater checks, Rust tests, and Cargo audit pass.
- [ ] `python scripts/version.py check` confirms every version surface matches `VERSION`.
- [ ] The Windows build produces exactly one NSIS installer and the sidecar/desktop smokes pass.
- [ ] The candidate workflow validates updater archive, signature, checksums, manifest, metadata, release notes, and creates only a draft prerelease.

## Clean Windows x64 gate

- [ ] Use a disposable, fully updated Windows 10 1809+ or Windows 11 x64 VM without Python, Node.js, Rust, Cargo, Git, or the repository.
- [ ] Install the unsigned internal artifact only for functional testing; use a code-signed artifact before public distribution.
- [ ] Confirm first run, onboarding, case/entity/relation creation, Canvas use, report creation, managed evidence ingestion, restart, persistence, and clean shutdown.
- [ ] Confirm the backend listens only on loopback and no backend process remains after normal close or uninstall.
- [ ] Confirm SQLite, configuration, evidence, logs, and backups are under `%APPDATA%\OIHK-Basic`.
- [ ] Confirm the installer contains no repository, `.env`, caches, development directories, private keys, tokens, or temporary files.
- [ ] Uninstall and confirm `%APPDATA%\OIHK-Basic` is preserved.

## Signed update gate

- [ ] Custodians supply `TAURI_SIGNING_PRIVATE_KEY` and its password through protected CI secrets; the public key is configured as `TAURI_UPDATER_PUBLIC_KEY`.
- [ ] A signed prior `0.1.0` build and signed `0.1.1-alpha.1` candidate are available in an isolated test channel.
- [ ] `latest-alpha.json`, installer, updater archive, signature, checksums, manifest, and notes are anonymously reachable over HTTPS.
- [ ] Validate availability-only check, notes, consent, progress, safe cancellation, valid signature, invalid signature, and hash mismatch.
- [ ] Validate pre-update backup, integrity check, busy SQLite/write draining, sidecar shutdown, install, restart, migration, and recovery after forced install/migration failures.
- [ ] Confirm cases, entities, relations, reports, evidence and hashes, Copilot history, settings, sources, audit history, and older backups survive.
- [ ] Uninstall the upgraded build and confirm application data remains.

## Publication gate

- [ ] Maintainer reviews dependency warnings and accepts or remediates each remaining item.
- [ ] Maintainer records artifact name, byte size, SHA-256, updater signature, build provenance, VM image, and validation date.
- [ ] Repository visibility or a separate public static host is approved so updater assets are anonymously available.
- [ ] Draft prerelease is reviewed and explicitly published as an alpha; no workflow promotes alpha/beta/stable automatically.
- [ ] Release notes state alpha risk, local storage, backup responsibility, legal/authorized-use scope, and known limitations.

Do not merge, tag, publish, or promote while any applicable gate above is unresolved.
