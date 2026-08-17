# Releasing signed OIHK Basic updates

## One-time signing setup

Generate the updater key on a protected maintainer workstation:

```powershell
cd frontend
npm exec tauri signer generate -- -w C:\protected\oihk-basic-updater.key
```

Store the private key and its password in a managed secret store. Configure GitHub:

- Actions secret `TAURI_SIGNING_PRIVATE_KEY`
- Actions secret `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`
- repository variable `TAURI_UPDATER_PUBLIC_KEY`

The public key is safe to embed. The private key must not be committed, pasted into issues or logs, uploaded as an artifact, or copied into the application data directory.

For key rotation, first ship a bridge version signed with the old private key that embeds the new public key. Only after that bridge is broadly installed may future releases be signed with the new key. Replacing both keys at once strands existing installations.

## Candidate flow

1. Change the root `VERSION` only, then run `python scripts/version.py sync`.
2. Add release notes under that exact version in `CHANGELOG.md`.
3. Run the complete local/CI validation in `docs/BUILDING.md`.
4. Create and push `basic-vX.Y.Z`.
5. `.github/workflows/release-windows.yml` validates the tag, Gitleaks, dependencies, lint, tests, Rust, frontend, PyInstaller sidecar smoke, signed NSIS build, signatures, checksums, JSON, and required artifacts.
6. The workflow creates or updates a **draft prerelease**. It never publishes it.

Required candidate assets:

- `OIHK Basic_X.Y.Z_x64-setup.exe`
- the Tauri `.nsis.zip` updater archive
- `.nsis.zip.sig`
- `latest-alpha.json`
- `release-manifest.json`
- SHA-256 files
- changelog-derived release notes

## Manual validation before publication

Use a disposable Windows Sandbox or clean VM.

**For the first published release there is no predecessor to upgrade from**, so
steps 1 and 3 have nothing to install or point at. Validate what that release
can actually demonstrate — clean install without Python, Node, Rust or the
repository; the fixture in step 2; startup; uninstall preserving
`%APPDATA%\OIHK-Basic` — and record the upgrade path as untested. The full
sequence below applies from the second signed candidate onward, which is the
first one that has something to upgrade *from*.

1. Install the previous signed candidate without Python, Node, Rust, or the repository.
2. Create the representative fixture: cases, entities, relationships, reports, managed evidence, Copilot conversations/messages, settings, audit history, sources, and an older backup.
3. Point the test build at a controlled HTTPS alpha endpoint containing the signed `0.1.1-alpha.2` candidate.
4. Confirm startup only reports availability.
5. Confirm release notes, date, size, progress, safe cancellation, retry, and explicit restart.
6. Confirm an invalid signature is blocked before backup/install.
7. Confirm a busy/write-drain failure leaves the application usable.
8. Complete the update and verify every fixture category plus evidence hashes.
9. Confirm migration history, pre-update metadata/SHA, local sanitized log, sidecar startup, and uninstall preservation of `%APPDATA%\OIHK-Basic`.
10. Exercise a forced install failure and a migration failure, then validate restart/recovery instructions.

`tests/test_update_upgrade_fixture.py` automates the data-preservation portion of `0.1.0 -> 0.1.1-alpha.1`; it does not replace the signed installer/VM test.

## Publish and promote

After all manual checks are recorded:

1. Publish the draft GitHub release as a prerelease.
2. Run **Promote tested update channel** manually with the published tag, channel, and confirmation `PROMOTE`.
3. That workflow re-downloads and validates the assets before updating the rolling `basic-alpha` metadata release.

The repository is public, so channel metadata is anonymously reachable and
that is no longer what blocks promotion; see `docs/UPDATES.md`. What blocks it
is having no published release to promote.

## Key handling

`TAURI_SIGNING_PRIVATE_KEY` and its password belong in **Actions secrets**.
Never place either in an Actions *variable*: variables are readable by anyone
with read access to the repository — everyone, on a public repo — and they are
not masked in workflow logs. Only `TAURI_UPDATER_PUBLIC_KEY` belongs in a
variable. This is written down because it already happened once.
