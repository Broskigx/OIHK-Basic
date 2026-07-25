# Installing OIHK Basic on Windows

## Requirements

- Windows 10 or 11 x64.
- WebView2 Runtime, normally included with current Windows versions.
- No Python, Node.js or administrator account is required.

## Install

1. Download `OIHK Basic_0.1.0_x64-setup.exe` from the `Broskigx/OIHK-Basic` Releases page.
2. Verify the adjacent `.sha256` file when supplied.
3. Run the installer. The default NSIS mode installs for the current user.
4. Launch OIHK Basic and complete or skip the onboarding.

Basic is monousuario and does not require an application login by default. The backend is packaged with the app and listens on a dynamic loopback port.

## Data

User data is separate from the installation at `%APPDATA%\OIHK-Basic\`:

- `oihk-basic.db`: SQLite database.
- `storage\`: managed evidence and imported files.
- `config\`: generated local secrets.

Uninstalling the executable preserves this directory. Use the in-app backup before manually removing it.

## Troubleshooting

- If the window cannot render, repair or install Microsoft Edge WebView2 Runtime.
- If startup reports a backend error, close all OIHK Basic processes and restart; the app chooses a new free port.
- Unsigned community builds can trigger SmartScreen or antivirus reputation checks. Verify the checksum and obtain releases only from the Basic repository.
