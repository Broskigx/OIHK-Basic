# Building OIHK Basic

OIHK Basic supports web development on Windows, Linux, and macOS. Desktop builders exist for all three platforms, but only Windows x64 has the current alpha packaging focus. A successful local build is not a release endorsement.

## Prerequisites

All platforms require:

- Python 3.11+
- Node.js 22 (`>=22 <23`)
- Rust stable and Cargo
- Git

Native Tauri requirements:

- Windows: Microsoft C++ Build Tools and WebView2
- Linux: WebKitGTK 4.1, GTK 3, librsvg2, patchelf, and OpenSSL development headers
- macOS: Xcode Command Line Tools

The frontend lockfile and Tauri CLI are repository-managed. The Windows backend lockfile is generated for Python 3.11 x64 and installed with hashes. Linux and macOS resolve native markers from `backend/pyproject.toml`; their builders are not yet declared fully reproducible release paths.

## Development

Install the backend and frontend dependencies from the repository root:

```powershell
python -m venv backend\.venv
.\backend\.venv\Scripts\python.exe -m pip install --upgrade pip
.\backend\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
cd frontend
npm ci
```

On Windows, `.\scripts\dev.ps1` starts the web frontend and backend and relays both outputs. The script accepts `-FrontendOnly` and `-BackendOnly`. On Linux or macOS, activate `backend/.venv` and run `python backend/run.py` and `npm run dev` in separate terminals.

For desktop development, start Vite first and then Tauri:

```powershell
# terminal 1
cd frontend
npm run dev

# terminal 2, with backend/.venv active
cd frontend
npm run desktop:dev
```

The Tauri debug process starts `backend/run.py`, chooses a free loopback port, waits for health, and terminates the managed process when the desktop shell exits.

## Windows local QA build

The supported local packaging entry point builds an **unsigned** NSIS installer with the updater disabled:

```powershell
cd frontend
npm run release:local
```

Equivalent root command:

```powershell
.\scripts\build-windows.ps1 -Release -Channel local -Unsigned -SkipUpdater
```

The pipeline validates the canonical version; installs locked Python dependencies; runs lint, tests, and dependency audits; builds the PyInstaller sidecar; builds the frontend; builds Tauri; copies the installer to `dist/windows`; verifies SHA-256; and runs sidecar/desktop smokes. The target machine does not need Python.

The resulting installer is for local QA. It is not signed with Authenticode, creates no updater artifact, and must not be presented as an official release.

## Signed alpha build

The signed updater path is intentionally fail-closed:

```powershell
$env:TAURI_SIGNING_PRIVATE_KEY = "<secret-store value>"
$env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD = "<secret-store value>"
$env:TAURI_UPDATER_PUBLIC_KEY = "<repository public variable>"
cd frontend
npm run release:alpha
```

Without all three values the build fails instead of falling back to unsigned artifacts. Tauri updater signing and Windows Authenticode signing are distinct; this path signs updater artifacts and does not provide executable reputation signing.

Release configuration is generated into an ignored overlay and never writes the private key to the repository. Distribution still requires the clean-VM and controlled-endpoint validation in [Releasing](RELEASING.md).

## Linux and macOS source builders

Run on the target platform:

```bash
# Linux
./scripts/build-linux.sh

# macOS, native architecture
./scripts/build-macos.sh
```

These scripts run platform gates, assemble a native sidecar, build the frontend and Tauri bundle, and generate checksums. They are development builders, not a promise that AppImage, deb, app, or dmg artifacts are available for download. See the [Linux](LINUX_INSTALL.md) and [macOS](MACOS_INSTALL.md) status pages.

## Outputs

Build outputs are ignored by Git:

```text
dist/
  sidecar/   # packaged local backend
  windows/   # NSIS installer and checksum
  linux/     # platform bundles and checksums when built on Linux
  macos/     # platform bundles and checksums when built on macOS
```

The canonical version comes from `VERSION`; `python scripts/version.py check` verifies synchronized metadata before packaging.

## Validation boundaries

- `scripts/smoke-sidecar.ps1` launches the packaged backend with isolated data and validates health plus pre-update backup integrity.
- `scripts/smoke-desktop.ps1` validates that the release desktop executable starts its adjacent sidecar, authorizes the Tauri origin, creates data in the expected root, and cleans up its process.
- `scripts/smoke_system_link_e2e.py` requires a separate local OIHK Evidence Lab checkout and validates the real pairing/authentication/capability boundary.
- Signed updater validation requires protected signing keys and a controlled public HTTPS endpoint.
- Installation, launch, upgrade, uninstall, rollback, and residue checks on clean machines remain manual release gates.

See [Release Checklist](RELEASE_CHECKLIST.md), [Releasing](RELEASING.md), and [Updater Design](UPDATES.md).
