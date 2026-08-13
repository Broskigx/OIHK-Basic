# Troubleshooting OIHK Basic

This guide targets source builds and controlled alpha candidates. Start with the visible error message: the application now preserves structured backend details where available.

## Development UI cannot reach the backend

Expected development addresses are `http://127.0.0.1:5173` for Vite and `http://127.0.0.1:8000` for FastAPI.

1. Open `http://127.0.0.1:8000/health` in a browser. A healthy service returns a JSON response.
2. Confirm no other process owns port `8000`.
3. Start only the backend with `.\scripts\dev.ps1 -BackendOnly` on Windows, or `python backend/run.py` with `backend/.venv` active.
4. Keep loopback names consistent. Custom CORS origins must be explicit in `.env`; do not solve a local error by exposing the backend publicly.

## Desktop window opens but the backend does not

- In development, activate `backend/.venv`, start Vite first, then run `npm run desktop:dev` from `frontend/`.
- A packaged build uses the sidecar. Run `scripts/smoke-sidecar.ps1` against the built executable before testing the installer.
- On Windows, WebView2 must be installed. Current Windows 10/11 systems usually include it.
- Close remaining OIHK Basic processes before retrying. Tauri chooses a free loopback port; it does not require port `8000` in packaged mode.

Do not attach raw logs to a public issue until you have checked them for paths, investigation names, model content, and personal data.

## LM Studio or Ollama is not detected

Detection checks `http://127.0.0.1:1234` for LM Studio and `http://127.0.0.1:11434` for Ollama.

- LM Studio: load a model and start the local OpenAI-compatible server.
- Ollama: install at least one model and run `ollama serve` if the service is not active.
- In **Local Models**, confirm the provider and endpoint, then select **List models**.
- If the catalog is empty, confirm the runtime itself exposes a model before changing OIHK settings.
- For a custom private address, enter it manually. Public hosts and credentials embedded in the URL are rejected by design.

## A model is detected but AI features fail

Detection and configuration do not prove inference. Select a model, save the configuration, and run **Test inference**.

- A timeout usually means the model is still loading, the hardware cannot respond within the configured period, or the runtime is stalled.
- A connection error means the saved endpoint is no longer reachable.
- An empty or malformed response means the runtime did not return the adapter's expected completion shape.
- Switching provider, endpoint, or model makes the form unsaved until it is saved again; repeat the inference test after any change.

OIHK Basic does not download models or silently fall back to a cloud provider.

## An empty workspace looks unexpected

- **Investigations:** clear active filters before assuming records are missing.
- **Graph:** select an investigation and add or explicitly promote entities; filters hide data but do not delete it.
- **Evidence:** clear filters. With no evidence at all, add a managed file from the Evidence workspace.
- **Local Models:** an empty catalog means no models were returned; it does not mean a model was selected automatically.

## Local data and recovery

Default data roots are:

- Windows: `%APPDATA%\OIHK-Basic\`
- Linux: `${XDG_DATA_HOME:-~/.local/share}/OIHK-Basic/`
- macOS: `~/Library/Application Support/OIHK-Basic/`

Keep an external backup before moving, deleting, or replacing these directories. A storage-directory change requires a backup and restart; live relocation is blocked intentionally. Uninstallers are expected to preserve user data, but this is alpha behavior and must be verified for each candidate.

## Reporting a reproducible issue

Include:

- OIHK Basic version and commit SHA
- operating system and architecture
- source, web-development, or packaged mode
- exact action and visible error
- whether a fresh disposable profile reproduces it
- relevant gate output or a sanitized diagnostic export

Never include API keys, real evidence, database files, model conversation content, Link Keys, private identity material, or unsanitized logs.
