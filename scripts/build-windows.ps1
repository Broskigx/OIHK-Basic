#!/usr/bin/env pwsh
# OIHK Basic - Windows Build Script
# Builds the complete application: backend sidecar + frontend + Tauri desktop

param(
    [switch]$Release,
    [ValidateSet("alpha", "beta", "stable", "local")]
    [string]$Channel = "alpha",
    [switch]$Unsigned,
    [switch]$SkipUpdater
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Local/unsigned builds never touch updater or signing artifacts.
$SkipUpdaterEffective = $SkipUpdater -or $Unsigned -or ($Channel -eq "local")
$NeedsUpdater = $Release -and -not $SkipUpdaterEffective

$ProjectRoot = Split-Path $PSScriptRoot -Parent
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$TauriDir = Join-Path $ProjectRoot "src-tauri"
$DistDir = Join-Path $ProjectRoot "dist"
$SidecarDir = Join-Path $DistDir "sidecar"
$ReleaseConfig = Join-Path $TauriDir "tauri.release.conf.json"
$RequirementsLock = Join-Path $BackendDir "requirements.lock"
$BuildStarted = Get-Date

function Assert-WorkspacePath([string]$Path) {
    $resolvedRoot = [System.IO.Path]::GetFullPath($ProjectRoot).TrimEnd('\') + '\'
    $resolvedPath = [System.IO.Path]::GetFullPath($Path)
    if (-not $resolvedPath.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing filesystem mutation outside the repository: $resolvedPath"
    }
}

Write-Host "=== OIHK Basic Build (Windows) ===" -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot" -ForegroundColor White
if ($NeedsUpdater) {
    Write-Host "Mode: signed release ($Channel, updater enabled)" -ForegroundColor Yellow
} else {
    Write-Host "Mode: local unsigned build (no updater, no signing keys)" -ForegroundColor Yellow
}
python (Join-Path $ProjectRoot "scripts\version.py") check
if ($LASTEXITCODE -ne 0) { throw "Version metadata validation failed." }

if ($NeedsUpdater) {
    if (-not $env:TAURI_SIGNING_PRIVATE_KEY) {
        throw "TAURI_SIGNING_PRIVATE_KEY is required for a signed updater release build. Configure TAURI_SIGNING_PRIVATE_KEY, TAURI_SIGNING_PRIVATE_KEY_PASSWORD and TAURI_UPDATER_PUBLIC_KEY (see docs/BUILDING.md), or run npm run release:local for an unsigned local build."
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
Set-Location $ProjectRoot
& $venvPython -m ruff check "$BackendDir\app" "$BackendDir\run.py" "$ProjectRoot\scripts" "$ProjectRoot\tests" --config "$BackendDir\pyproject.toml" --quiet
if ($LASTEXITCODE -ne 0) { throw "Python lint failed." }
Write-Host "  Lint passed" -ForegroundColor Green

# 5. Run backend tests
#
# The test paths are named explicitly, exactly as CI names them, and that is
# not cosmetic. pytest derives its rootdir from the arguments it is given:
# with `backend/tests` among them it finds `backend/pyproject.toml` and applies
# `asyncio_mode = "auto"`; invoked bare from the project root it finds no
# config at all, falls back to strict mode, and every sync test that uses an
# async fixture errors at setup. That is what happened — CI was green on
# `pytest backend/tests tests` while this build failed 132 tests on `pytest`,
# so a green CI said nothing about whether a release would build.
Write-Host "`n[5/8] Running backend tests..." -ForegroundColor Yellow
Set-Location $ProjectRoot
& $venvPython -m pytest (Join-Path $BackendDir "tests") (Join-Path $ProjectRoot "tests") --quiet --tb=short --no-header 2>&1
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
$tauriConfig = if ($NeedsUpdater) { "src-tauri/tauri.release.conf.json" } else { "src-tauri/tauri.local.conf.json" }
if ($NeedsUpdater) {
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
    $oldName = "windows-old-" + (Get-Date -Format "yyyyMMdd-HHmmssfff")
    Rename-Item -LiteralPath $windowsDist -NewName $oldName
    Write-Host "  Archived previous build output to dist\$oldName" -ForegroundColor Yellow
}
New-Item -ItemType Directory -Force -Path $windowsDist | Out-Null
Copy-Item $installerSource.FullName $windowsDist -Force
if (-not (Test-Path -LiteralPath (Join-Path $windowsDist $installerSource.Name))) {
    throw "The installer was not copied to dist\windows."
}
Write-Host "  Installer: $($installerSource.Name)" -ForegroundColor Green
if ($NeedsUpdater) {
    Get-ChildItem "$bundleDir\*.nsis.zip*" | Copy-Item -Destination $windowsDist -Force
}
& (Join-Path $ProjectRoot "scripts\smoke-installer.ps1") `
    -InstallerPath (Join-Path $windowsDist $installerSource.Name)
if ($LASTEXITCODE -ne 0) { throw "Clean NSIS installer smoke test failed." }

# Generate SHA-256 and verify the installer was produced by this run
$artifacts = Get-ChildItem (Join-Path $DistDir "windows\") -Filter "*.exe"
if (-not $artifacts) { throw "No installer was produced in dist\windows." }
$newestInstaller = $artifacts | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($newestInstaller.Length -le 0) { throw "The generated installer is empty." }
if ($newestInstaller.LastWriteTime -lt $BuildStarted) {
    throw "The installer in dist\windows predates this build run; refusing stale artifacts."
}
Write-Host "  New installer: $($newestInstaller.Name) ($($newestInstaller.Length) bytes)" -ForegroundColor Green
foreach ($artifact in $artifacts) {
    $hash = Get-FileHash $artifact.FullName -Algorithm SHA256
    "$($hash.Hash)  $($artifact.Name)" | Out-File "$($artifact.FullName).sha256" -Encoding ascii
    Write-Host "  SHA256 ($($artifact.Name)): $($hash.Hash)" -ForegroundColor Green
}
$shaText = (Get-Content -LiteralPath "$($newestInstaller.FullName).sha256" -Raw).Trim()
$computedHash = (Get-FileHash $newestInstaller.FullName -Algorithm SHA256).Hash
if (-not $shaText.StartsWith($computedHash, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "The generated .sha256 sidecar does not match the installer hash."
}

if ($NeedsUpdater) {
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
    if ($LASTEXITCODE -ne 0) { throw "Update metadata generation failed." }
    python (Join-Path $ProjectRoot "scripts\validate_release_artifacts.py") $windowsDist --channel $Channel
    if ($LASTEXITCODE -ne 0) { throw "Release artifact validation failed." }
}

Write-Host "`n=== Build complete! ===" -ForegroundColor Cyan
Write-Host "Installer: $DistDir\windows\" -ForegroundColor White
Set-Location $ProjectRoot
