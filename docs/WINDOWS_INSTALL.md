# Windows alpha-candidate installation

There is no generally supported OIHK Basic installer. This procedure is for an explicitly approved Windows x64 alpha candidate produced by the repository's release process. GitHub Actions artifacts and local unsigned builds are not official releases.

## Requirements

- Windows 10 or 11 x64
- WebView2 Runtime, normally included with current Windows versions
- A disposable test profile and external backup location

Python, Node.js, and an administrator account are not required for a packaged build.

## Candidate validation

1. Obtain `OIHK Basic_0.1.1-alpha.2_x64-setup.exe` and its checksum from the candidate location named by the maintainer.
2. Verify the SHA-256 value before running the file.
3. Confirm whether the candidate has Authenticode signing. Updater signing does not imply executable signing, and an unsigned build may trigger SmartScreen.
4. Install for the current user, launch, and complete or skip onboarding using disposable data.
5. Run the install, upgrade, uninstall, and residue checks in [Release Checklist](RELEASE_CHECKLIST.md).

The packaged backend listens on a dynamically selected loopback port and is supervised by the desktop process.

## User data

The default data root is `%APPDATA%\OIHK-Basic\` and includes the SQLite database, managed storage, local configuration, updater recovery state, and sanitized updater logs.

Uninstall is designed to preserve that directory. Because the product is alpha, verify that behavior for every candidate and keep a tested backup before installing, upgrading, or removing it.

## Problems

- If the window cannot render, repair or install Microsoft Edge WebView2 Runtime.
- If startup reports a backend error, close all OIHK Basic processes and retry; the packaged app chooses a free loopback port.
- Do not bypass SmartScreen for an artifact whose source and checksum you cannot verify.
- See [Troubleshooting](TROUBLESHOOTING.md) before sharing sanitized diagnostics.
