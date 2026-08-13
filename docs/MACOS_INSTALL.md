# macOS build and installation status

OIHK Basic does not currently publish a signed, notarized, release-ready macOS app. Do not assume Intel or Apple Silicon dmg files are available from the Releases page, and do not instruct testers to remove quarantine attributes as a substitute for signing and notarization.

## Build from source

On a supported macOS development host, install Python 3.11+, Node.js 22, Rust, and Xcode Command Line Tools. Run:

```bash
./scripts/build-macos.sh
```

The builder targets the host architecture, runs quality gates, assembles a PyInstaller sidecar, builds the frontend and Tauri bundle, and places generated artifacts/checksums under `dist/macos/`.

Treat the result as a local development build. Distribution still requires:

- clean builds and launch tests on Intel and Apple Silicon targets;
- an Apple Developer identity and hardened runtime configuration;
- code signing and notarization of the final app/bundle;
- Gatekeeper validation on clean machines;
- install, upgrade, uninstall, data-preservation, and residue checks.

The default data root is `~/Library/Application Support/OIHK-Basic/`. Keep a verified backup before testing a candidate.

See [Building](BUILDING.md), [Known Limitations](KNOWN_LIMITATIONS.md), and [Troubleshooting](TROUBLESHOOTING.md).
