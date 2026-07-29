#!/usr/bin/env pwsh
# OIHK Basic - Windows Build Script
# Builds the complete application: backend sidecar + frontend + Tauri desktop

param(
    [switch]$Release,
    [ValidateSet("alpha", "beta", "stable")]
    [string]$Channel = "alpha"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$TauriDir = Join-Path $ProjectRoot "src-tauri"
$DistDir = Join-Path $ProjectRoot "dist"
$SidecarDir = Join-Path $DistDir "sidecar"
$ReleaseConfig = Join-Path $TauriDir "tauri.release.conf.json"
$RequirementsLock = Join-Path $BackendDir "requirements.lock"

function Assert-WorkspacePath([string]$Path) {
    $resolvedRoot = [System.IO.Path]::GetFullPath($ProjectRoot).TrimEnd('\') + '\'
    $resolvedPath = [System.IO.Path]::GetFullPath($Path)
    if (-not $resolvedPath.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing filesystem mutation outside the repository: $resolvedPath"
    }
}

Write-Host "=== OIHK Basic Build (Windows) ===" -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot" -ForegroundColor White
python (Join-Path $ProjectRoot "scripts\version.py") check
if ($LASTEXITCODE -ne 0) { throw "Version metadata validation failed." }

if ($Release) {
    if (-not $env:TAURI_SIGNING_PRIVATE_KEY) {
        throw "TAURI_SIGNING_PRIVATE_KEY is required for a signed updater release build."
    }
    if (-not $env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD) {
        throw "TAURI_SIGNING_PRIVATE_KEY_PASSWORD is required for a signed updater release build."
    }
    if (-not $env:TAURI_UPDATER_PUBLIC_KEY) {
        throw "TAURI_UPDATER_PUBLIC_KEY is required for a signed updater release build."
    }
    python (Join-Path $ProjectRoot "scripts\generate_release_config.py") --channel $Channel
    if ($LASTEXITCODE -ne 0) { throw "Updater release configuration failed." }
}

# 1. Verify tools
Write-Host "`n[1/8] Verifying tools..." -ForegroundColor Yellow
$tools = @("python", "npm", "cargo")
foreach ($tool in $tools) {
    try {
        $version = & $tool --version 2>&1 | Select-Object -First 1
        Write-Host "  [ok] $version" -ForegroundColor Green
    } catch {
        Write-Host "  [error] $tool not found. Install it first." -ForegroundColor Red
        exit 1
    }
}

# 2. Create virtual environment
Write-Host "`n[2/8] Setting up Python virtual environment..." -ForegroundColor Yellow
$venvDir = Join-Path $BackendDir "venv"
if (-not (Test-Path $venvDir)) {
    python -m venv $venvDir
    Write-Host "  Created virtual environment" -ForegroundColor Green
}

$venvPython = Join-Path $venvDir "Scripts\python.exe"

# 3. Install Python dependencies
Write-Host "`n[3/8] Installing Python dependencies..." -ForegroundColor Yellow
& $venvPython -m pip install --disable-pip-version-check --require-hashes -r $RequirementsLock --quiet
if ($LASTEXITCODE -ne 0) { throw "Locked Python dependency installation failed." }
& $venvPython -m pip install --disable-pip-version-check --no-build-isolation --no-deps -e $BackendDir --quiet
if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed." }
Write-Host "  Done" -ForegroundColor Green
& $venvPython -m pip_audit -r $RequirementsLock
if ($LASTEXITCODE -ne 0) { throw "Python dependency audit failed." }

# 4. Run lint
Write-Host "`n[4/8] Running lint..." -ForegroundColor Yellow
& $venvPython -m ruff check "$BackendDir\app" "$BackendDir\run.py" "$ProjectRoot\scripts" "$ProjectRoot\tests" --quiet
if ($LASTEXITCODE -ne 0) { throw "Python lint failed." }
Write-Host "  Lint passed" -ForegroundColor Green

# 5. Run backend tests
Write-Host "`n[5/8] Running backend tests..." -ForegroundColor Yellow
Set-Location $ProjectRoot
& $venvPython -m pytest --quiet --tb=short --no-header 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [error] Tests failed" -ForegroundColor Red
    exit 1
}
Write-Host "  Tests passed" -ForegroundColor Green

# 6. Build backend sidecar with PyInstaller
Write-Host "`n[6/8] Building backend sidecar..." -ForegroundColor Yellow
Set-Location $ProjectRoot
# Clean previous build
$pyiBuild = Join-Path $ProjectRoot "build"
$pyiDist = Join-Path $ProjectRoot "dist\sidecar"
Assert-WorkspacePath $pyiBuild
Assert-WorkspacePath $pyiDist
if (Test-Path $pyiBuild) { Remove-Item -Recurse -Force $pyiBuild }
if (Test-Path $pyiDist) { Remove-Item -Recurse -Force $pyiDist }

& $venvPython -m PyInstaller oihk-basic-backend.spec --clean --noconfirm --distpath "$SidecarDir"
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [error] PyInstaller build failed" -ForegroundColor Red
    exit 1
}

# Keep an extensionless resource name so the same Tauri manifest works on every OS.
Copy-Item "$pyiDist\oihk-basic-backend.exe" "$pyiDist\oihk-basic-backend" -Force
$cargoPath = (Get-Command cargo -ErrorAction Stop).Source
$rustcPath = Join-Path (Split-Path $cargoPath -Parent) "rustc.exe"
if (-not (Test-Path -LiteralPath $rustcPath)) {
    $rustcPath = (Get-Command rustc -ErrorAction Stop).Source
}
$rustVersion = & $rustcPath -vV 2>&1
$hostLine = $rustVersion | Select-String '^host:' | Select-Object -First 1
if (-not $hostLine) {
    throw "Unable to determine the Rust host target triple."
}
$targetTriple = ($hostLine.ToString().Split(':', 2)[1]).Trim()
Copy-Item "$pyiDist\oihk-basic-backend.exe" "$pyiDist\oihk-basic-backend-$targetTriple.exe" -Force
Write-Host "  Sidecar built: $pyiDist\oihk-basic-backend.exe" -ForegroundColor Green
& (Join-Path $ProjectRoot "scripts\smoke-sidecar.ps1") -SidecarPath "$pyiDist\oihk-basic-backend.exe"
if ($LASTEXITCODE -ne 0) { throw "Packaged sidecar smoke test failed." }

# 7. Build frontend
Write-Host "`n[7/8] Building frontend..." -ForegroundColor Yellow
Set-Location $FrontendDir
npm ci --silent
if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [error] Frontend build failed" -ForegroundColor Red
    exit 1
}
Write-Host "  Frontend built" -ForegroundColor Green

# 8. Build Tauri desktop app
Write-Host "`n[8/8] Building Tauri desktop app..." -ForegroundColor Yellow
Set-Location $TauriDir
Set-Location $ProjectRoot
# Keep release builds reliable on the documented 4 GB minimum. Callers can
# explicitly raise this when they control a larger CI runner.
if (-not $env:CARGO_BUILD_JOBS) {
    $env:CARGO_BUILD_JOBS = "1"
}
Write-Host "  Rust build jobs: $env:CARGO_BUILD_JOBS" -ForegroundColor DarkGray
$bundleDir = Join-Path $TauriDir "target\release\bundle\nsis"
Assert-WorkspacePath $bundleDir
if (Test-Path -LiteralPath $bundleDir) {
    Remove-Item -LiteralPath $bundleDir -Recurse -Force
}
$tauriConfig = if ($Release) { "src-tauri/tauri.release.conf.json" } else { "src-tauri/tauri.sidecar.conf.json" }
if ($Release) {
    & (Join-Path $FrontendDir "node_modules\.bin\tauri.cmd") build --bundles nsis --config $tauriConfig --features updater-release --ci
} else {
    & (Join-Path $FrontendDir "node_modules\.bin\tauri.cmd") build --bundles nsis --config $tauriConfig --ci
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [error] Tauri build failed" -ForegroundColor Red
    exit 1
}
& (Join-Path $ProjectRoot "scripts\smoke-desktop.ps1") `
    -DesktopPath (Join-Path $TauriDir "target\release\oihk-basic-desktop.exe")
if ($LASTEXITCODE -ne 0) { throw "Release desktop smoke test failed." }

# Copy installer to dist
$tauriTarget = Join-Path $TauriDir "target\release"
$installerCandidates = @(Get-ChildItem -LiteralPath $bundleDir -Filter "*.exe" -File)
if ($installerCandidates.Count -ne 1) {
    throw "Expected exactly one NSIS installer, found $($installerCandidates.Count)."
}
$installerSource = $installerCandidates[0]
$windowsDist = Join-Path $DistDir "windows"
Assert-WorkspacePath $windowsDist
if (Test-Path -LiteralPath $windowsDist) {
    Remove-Item -LiteralPath $windowsDist -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $windowsDist | Out-Null
Copy-Item $installerSource.FullName $windowsDist -Force
Write-Host "  Installer: $($installerSource.Name)" -ForegroundColor Green
if ($Release) {
    Get-ChildItem "$bundleDir\*.nsis.zip*" | Copy-Item -Destination $windowsDist -Force
}
& (Join-Path $ProjectRoot "scripts\smoke-installer.ps1") `
    -InstallerPath (Join-Path $windowsDist $installerSource.Name)
if ($LASTEXITCODE -ne 0) { throw "Clean NSIS installer smoke test failed." }

# Generate SHA-256
$artifacts = Get-ChildItem (Join-Path $DistDir "windows\") -Filter "*.exe"
foreach ($artifact in $artifacts) {
    $hash = Get-FileHash $artifact.FullName -Algorithm SHA256
    "$($hash.Hash)  $($artifact.Name)" | Out-File "$($artifact.FullName).sha256" -Encoding ascii
    Write-Host "  SHA256 ($($artifact.Name)): $($hash.Hash)" -ForegroundColor Green
}

if ($Release) {
    $updaterArchive = Get-ChildItem "$windowsDist\*.nsis.zip" | Select-Object -First 1
    $updaterSignature = Get-ChildItem "$windowsDist\*.nsis.zip.sig" | Select-Object -First 1
    if (-not $installerSource -or -not $updaterArchive -or -not $updaterSignature) {
        throw "Signed NSIS updater artifacts are incomplete."
    }
    & cargo run --quiet --locked --manifest-path (Join-Path $TauriDir "Cargo.toml") `
        --example verify_update_signature -- `
        $updaterArchive.FullName $updaterSignature.FullName $env:TAURI_UPDATER_PUBLIC_KEY
    if ($LASTEXITCODE -ne 0) { throw "Updater signature does not match the archive and configured public key." }
    $version = (Get-Content (Join-Path $ProjectRoot "VERSION") -Raw).Trim()
    python (Join-Path $ProjectRoot "scripts\generate_update_metadata.py") `
        --tag "basic-v$version" `
        --channel $Channel `
        --installer (Join-Path $windowsDist $installerSource.Name) `
        --updater $updaterArchive.FullName `
        --signature $updaterSignature.FullName `
        --output-dir $windowsDist
    python (Join-Path $ProjectRoot "scripts\validate_release_artifacts.py") $windowsDist --channel $Channel
    if ($LASTEXITCODE -ne 0) { throw "Release artifact validation failed." }
}

Write-Host "`n=== Build complete! ===" -ForegroundColor Cyan
Write-Host "Installer: $DistDir\windows\" -ForegroundColor White
Set-Location $ProjectRoot
