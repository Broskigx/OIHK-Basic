# Installing OIHK Basic on macOS

## System Requirements

- macOS 10.15 (Catalina) or later
- Intel x64 or Apple Silicon (arm64)
- ~500 MB free disk space

## Installation

1. Download the appropriate `.dmg` for your Mac:
   - **Intel Macs:** `OIHK-Basic_0.1.1-alpha.2_x64.dmg`
   - **Apple Silicon Macs:** `OIHK-Basic_0.1.1-alpha.2_arm64.dmg`
2. Open the `.dmg` file
3. Drag "OIHK Basic.app" to your Applications folder
4. Launch from Applications or via Spotlight

### Gatekeeper Warning (Unsigned Builds)

If you see "OIHK Basic can't be opened because the developer cannot be verified":

1. Open System Settings → Privacy & Security
2. Scroll to "Security"
3. Click "Open Anyway" next to "OIHK Basic"
4. Click "Open" in the confirmation dialog

This warning appears because the application is not signed with an Apple Developer certificate. See [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md) for codesigning instructions.

## First Run

1. Launch "OIHK Basic" from Applications
2. The application will:
   - Generate secure encryption keys
   - Initialize the local database
   - Start the backend engine on a local port
3. Complete or skip onboarding; no account is required in the default loopback-only desktop mode
4. Start investigating!

## Data Location

All your data is stored in: `~/Library/Application Support/OIHK-Basic/`

## Uninstallation

1. Drag "OIHK Basic.app" from Applications to Trash
2. Optionally delete `~/Library/Application Support/OIHK-Basic/` to remove all data

## Troubleshooting

### App won't open
- Check Console.app for crash reports
- Verify the app is not quarantined: `xattr -d com.apple.quarantine /Applications/OIHK\ Basic.app`

### Backend fails
- Check logs in `~/Library/Application Support/OIHK-Basic/logs/`
- Ensure no other app is using the default port
