# Installing OIHK Basic on Linux

## System Requirements

- Linux x86_64
- WebKit2GTK 4.1+
- GTK 3
- ~500 MB free disk space

## Installation Methods

### AppImage (Recommended)

1. Download `OIHK-Basic_0.1.1-alpha.2_amd64.AppImage` from the Releases page
2. Make it executable: `chmod +x OIHK-Basic_0.1.1-alpha.2_amd64.AppImage`
3. Run it: `./OIHK-Basic_0.1.1-alpha.2_amd64.AppImage`

### Debian/Ubuntu Package

1. Download `OIHK-Basic_0.1.1-alpha.2_amd64.deb`
2. Install: `sudo dpkg -i OIHK-Basic_0.1.1-alpha.2_amd64.deb`
3. Or: `sudo apt install ./OIHK-Basic_0.1.1-alpha.2_amd64.deb`
4. Launch from the application menu or via `oihk-basic`

## First Run

1. Launch "OIHK Basic" from your application menu
2. The application will:
   - Generate secure encryption keys
   - Initialize the local database
   - Start the backend engine on a local port
3. Complete or skip onboarding; no account is required in the default loopback-only desktop mode
4. Start investigating!

## Data Location

All your data is stored in: `~/.local/share/OIHK-Basic/`

Or, if `$XDG_DATA_HOME` is set: `$XDG_DATA_HOME/OIHK-Basic/`

## Uninstallation

### AppImage
- Delete the AppImage file
- Optionally delete `~/.local/share/OIHK-Basic/` to remove all data

### Debian package
```bash
sudo apt remove oihk-basic
```
Your data is preserved. To delete data: `rm -rf ~/.local/share/OIHK-Basic/`
