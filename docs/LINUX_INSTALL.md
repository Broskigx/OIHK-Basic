# Linux build and installation status

OIHK Basic does not currently publish a release-ready or generally recommended Linux package. Do not assume an AppImage or deb is available from the Releases page.

Linux x86_64 is exercised as a backend portability target in standard CI. The desktop builder exists for contributors who can validate the result on their own system.

## Build from source

Install Python 3.11+, Node.js 22, Rust, WebKitGTK 4.1, GTK 3, librsvg2, patchelf, and OpenSSL development headers. Then run from the repository root:

```bash
./scripts/build-linux.sh
```

The script runs quality gates, builds the PyInstaller sidecar and frontend, invokes Tauri, and places any generated bundles/checksums under `dist/linux/`. Exact native package names depend on the Tauri toolchain and target.

Treat all resulting artifacts as local development builds. Before distribution, Linux still needs reproducible native dependency locking, clean-machine AppImage/deb install and launch checks, desktop integration tests, uninstall/residue verification, and a documented signing/publication policy.

## Development data

The default data root is `${XDG_DATA_HOME:-~/.local/share}/OIHK-Basic/`. Never remove that directory as part of an ordinary package uninstall. Back it up and inspect its resolved path before any manual cleanup.

See [Building](BUILDING.md), [Known Limitations](KNOWN_LIMITATIONS.md), and [Troubleshooting](TROUBLESHOOTING.md).
