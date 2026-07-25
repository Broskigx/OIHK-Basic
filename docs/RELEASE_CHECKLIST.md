# OIHK Basic — Release Checklist

## Windows verification — 2026-07-23

- [x] Root, backend and frontend test suites pass on Windows x64.
- [x] Ruff, ESLint, TypeScript/Vite and `cargo check` pass.
- [x] npm production dependency audit reports zero vulnerabilities.
- [x] PyInstaller sidecar starts without a Python installation dependency.
- [x] NSIS includes the sidecar and passes install, managed startup, health and uninstall smoke tests.
- [x] Installer SHA-256 is generated in `dist/windows/`.
- [ ] Code signing and SmartScreen reputation are not configured.
- [ ] Linux and macOS artifacts require native builders and tests.

## Pre-Release

- [ ] All tests pass on all platforms
- [ ] No hardcoded secrets or paths
- [ ] Version bumped in:
  - `backend/pyproject.toml`
  - `frontend/package.json`
  - `src-tauri/tauri.conf.json`
  - `src-tauri/Cargo.toml`
  - `backend/app/main.py` (VERSION constant)
- [ ] CHANGELOG updated
- [ ] All stubs documented in KNOWN_LIMITATIONS.md

## Build

### Windows (x64)
- [ ] Build: `.\scripts\build-windows.ps1`
- [ ] Installer generated: `dist/windows/OIHK-Basic_{version}_x64-setup.exe`
- [ ] SHA-256 generated: `OIHK-Basic_{version}_x64-setup.exe.sha256`
- [ ] Test installation on clean Windows VM
- [ ] Verify uninstall preserves user data

### Linux (x86_64)
- [ ] Build: `./scripts/build-linux.sh`
- [ ] AppImage generated: `dist/linux/OIHK-Basic_{version}_amd64.AppImage`
- [ ] .deb generated: `dist/linux/OIHK-Basic_{version}_amd64.deb`
- [ ] SHA-256 generated for both artifacts
- [ ] Test on Ubuntu 22.04+

### macOS Intel (x86_64)
- [ ] Build on macos-13 runner: `./scripts/build-macos.sh`
- [ ] .app bundle generated: `dist/macos/x64/OIHK Basic.app`
- [ ] .dmg generated: `dist/macos/x64/OIHK-Basic_{version}_x64.dmg`
- [ ] SHA-256 generated

### macOS Apple Silicon (arm64)
- [ ] Build on macos-14 runner: `./scripts/build-macos.sh`
- [ ] .app bundle generated: `dist/macos/arm64/OIHK Basic.app`
- [ ] .dmg generated: `dist/macos/arm64/OIHK-Basic_{version}_arm64.dmg`
- [ ] SHA-256 generated

## Codesigning (macOS Only)

Codesigning requires an Apple Developer account:
1. Enroll in Apple Developer Program ($99/year)
2. Create a Developer ID Application certificate
3. Sign the .app:
   ```bash
   codesign --force --deep --sign "Developer ID Application: Your Name" "OIHK Basic.app"
   ```
4. Notarize the .dmg:
   ```bash
   xcrun notarytool submit OIHK-Basic_{version}_x64.dmg \
     --apple-id your@email.com \
     --team-id YOUR_TEAM_ID \
     --password @keychain:notarytool-password
   ```
5. Wait for notarization and staple:
   ```bash
   xcrun stapler staple OIHK-Basic_{version}_x64.dmg
   ```

## Release

- [ ] Create GitHub tag: `git tag basic-v{version}`
- [ ] Push tag: `git push origin basic-v{version}`
- [ ] GitHub Actions will build all platforms automatically
- [ ] Verify all artifacts uploaded to release
- [ ] Download and test artifacts
- [ ] Publish release (mark as non-draft)

## Post-Release

- [ ] Update documentation if needed
- [ ] Announce release
- [ ] Monitor issue tracker for feedback
