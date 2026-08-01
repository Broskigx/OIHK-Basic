# Building OIHK Basic

## Requisitos

- Python 3.11 o superior.
- Node.js 22 (el `engines` de `frontend/package.json` exige `>=22 <23`; Vite 7 no soporta Node 18).
- Rust estable y Cargo.
- Herramientas nativas de compilación de la plataforma.
- Windows: Microsoft C++ Build Tools y WebView2.
- Linux: WebKitGTK 4.1, GTK 3, librsvg2, patchelf y OpenSSL headers.
- macOS: Xcode Command Line Tools.

Los scripts instalan PyInstaller dentro del entorno Python que utilizan. Tauri CLI está fijado en las dependencias de frontend. El flujo Windows instala `backend/requirements.lock` con hashes; ese lock se genera y valida para Python 3.11 en Windows x64, el target de distribución alpha. Linux y macOS resuelven sus marcadores nativos desde `pyproject.toml` y no se declaran reproducibles hasta conservar locks generados en sus runners.

## Build reproducible

Desde la raíz:

```powershell
# Windows
.\scripts\build-windows.ps1
```

### Build local sin firma (QA y pruebas)

No genera artefactos del updater, no requiere ninguna clave privada y es la vía recomendada para probar el instalador localmente:

```powershell
cd frontend
npm run release:local
```

Equivalente a:

```powershell
.\scripts\build-windows.ps1 -Release -Channel local -Unsigned -SkipUpdater
```

Este modo: compila frontend y sidecar PyInstaller, desactiva `createUpdaterArtifacts` (overlay `src-tauri/tauri.local.conf.json`), genera el instalador NSIS, lo copia a `dist/windows`, calcula y verifica el SHA-256 y ejecuta los smoke tests. El instalador **no está firmado** (ni updater ni Authenticode) y no debe distribuirse públicamente. Las claves de firma no son necesarias; el script falla con un mensaje claro si intenta usarse un modo firmado sin claves.

`npm run tauri:build` compila únicamente el binario Tauri con el overlay local (incluye el sidecar ya construido en `dist/sidecar/`). Para el pipeline completo usa `npm run release:local`.

### Release alpha firmado (updater)

```powershell
cd frontend
npm run release:alpha
```

Equivalente a:

```powershell
$env:TAURI_SIGNING_PRIVATE_KEY = "<secret-store value>"
$env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD = "<secret-store value>"
$env:TAURI_UPDATER_PUBLIC_KEY = "<repository public variable>"
.\scripts\build-windows.ps1 -Release -Channel alpha
```

Este modo verifica las tres variables, genera el overlay `src-tauri/tauri.release.conf.json` (ignorado por Git) con `createUpdaterArtifacts: true`, activa la feature `updater-release`, produce `.nsis.zip` + `.sig` y el JSON de metadatos del canal. Sin las claves **falla** con un mensaje claro; nunca degrada silenciosamente a un build sin firmar.

**Diferencia entre firmas:** la firma del updater de Tauri (Minisign sobre `.nsis.zip`) y la firma Authenticode del ejecutable de Windows son cosas distintas. El pipeline actual firma el artefacto del **updater**; no firma el ejecutable con un certificado de código. No asumas que el instalador está firmado con Authenticode.

El script genera un overlay Tauri ignorado por Git. No escribe la clave privada en disco.

```bash
# Linux
./scripts/build-linux.sh

# macOS, arquitectura nativa
./scripts/build-macos.sh
```

Cada script ejecuta lint, pruebas y auditorías de Python/npm, compila el backend con PyInstaller, genera el nombre de sidecar requerido por el target triple de Rust, compila frontend, construye Tauri y calcula SHA-256 de los artefactos. CI añade `cargo audit` sobre `Cargo.lock`; las advertencias de mantenimiento transitivas se revisan por separado de vulnerabilidades explotables.

## Artefactos

```text
dist/
  sidecar/   # backend intermedio; no se publica en Git
  windows/   # instalador NSIS y checksum
  linux/     # AppImage/deb y checksums
  macos/     # app/dmg por arquitectura y checksums
```

El build Windows base produce `OIHK Basic_0.1.1-alpha.2_x64-setup.exe`. El candidato con updater firmado no se declara validado hasta completar el checklist manual con claves y endpoint de prueba.

## Pasos manuales

El nombre/version del instalador procede de `VERSION`. El build de release exige el instalador NSIS, `.nsis.zip`, `.sig`, checksums y JSON consistentes. `smoke-sidecar.ps1` arranca el ejecutable PyInstaller de forma aislada y comprueba `/health` sin depender de Python instalado.

La compilación automática no sustituye la validación manual del upgrade firmado en Windows Sandbox descrita en [RELEASING.md](RELEASING.md). Ese control permanece pendiente hasta disponer de claves de producción y un endpoint HTTPS accesible para el cliente.

```powershell
python -m pip install --require-hashes -r .\backend\requirements.lock
python -m pip install --no-build-isolation --no-deps -e .\backend
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

Véase [RELEASING.md](RELEASING.md) y [UPDATES.md](UPDATES.md). La configuración Tauri de release es generada, contiene solo la clave pública y permanece ignorada por Git.

Véase [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md). Los artefactos, bases locales, evidencia, dependencias, caches y secretos permanecen ignorados por Git.
