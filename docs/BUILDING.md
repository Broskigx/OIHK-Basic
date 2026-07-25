# Building OIHK Basic

## Requisitos

- Python 3.11 o superior.
- Node.js 18 o superior.
- Rust estable y Cargo.
- Herramientas nativas de compilación de la plataforma.
- Windows: Microsoft C++ Build Tools y WebView2.
- Linux: WebKitGTK 4.1, GTK 3, librsvg2, patchelf y OpenSSL headers.
- macOS: Xcode Command Line Tools.

Los scripts instalan PyInstaller dentro del entorno Python que utilizan. Tauri CLI está fijado en las dependencias de frontend.

## Build reproducible

Desde la raíz:

```powershell
# Windows
.\scripts\build-windows.ps1
```

```bash
# Linux
./scripts/build-linux.sh

# macOS, arquitectura nativa
./scripts/build-macos.sh
```

Cada script ejecuta lint y pruebas, compila el backend con PyInstaller, genera el nombre de sidecar requerido por el target triple de Rust, compila frontend, construye Tauri y calcula SHA-256 de los artefactos.

## Artefactos

```text
dist/
  sidecar/   # backend intermedio; no se publica en Git
  windows/   # instalador NSIS y checksum
  linux/     # AppImage/deb y checksums
  macos/     # app/dmg por arquitectura y checksums
```

El build Windows verificado produce `OIHK Basic_0.1.0_x64-setup.exe`. El instalador se probó mediante instalación silenciosa, arranque directo del sidecar, arranque del backend administrado por Tauri y desinstalación.

## Pasos manuales

```powershell
python -m pip install -e ".\backend"
python -m pip install pyinstaller
python -m PyInstaller oihk-basic-backend.spec --clean --noconfirm `
  --distpath dist\sidecar --workpath build\pyinstaller

cd frontend
npm ci
npm run build
cd ..

# Copiar el sidecar al nombre con target triple antes de Tauri.
Copy-Item dist\sidecar\oihk-basic-backend.exe `
  dist\sidecar\oihk-basic-backend-x86_64-pc-windows-msvc.exe

.\frontend\node_modules\.bin\tauri.cmd build --bundles nsis `
  --config src-tauri/tauri.sidecar.conf.json
```

En Linux y macOS el sufijo se obtiene con `rustc -vV` y el binario no lleva `.exe`.

## Desarrollo de escritorio

El modo debug busca `backend/run.py` y usa Python del entorno:

```powershell
cd frontend
npm run desktop:dev
```

El modo release no depende de Python: localiza el sidecar empaquetado, selecciona un puerto libre de `127.0.0.1`, espera `/health` y termina el proceso hijo al cerrar la ventana.

## Release checklist

Véase [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md). Los artefactos, bases locales, evidencia, dependencias, caches y secretos permanecen ignorados por Git.
