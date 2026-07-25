#!/usr/bin/env pwsh
# OIHK Basic - Windows Build Script
# Builds the complete application: backend sidecar + frontend + Tauri desktop

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$TauriDir = Join-Path $ProjectRoot "src-tauri"
$DistDir = Join-Path $ProjectRoot "dist"
$SidecarDir = Join-Path $DistDir "sidecar"

Write-Host "=== OIHK Basic Build (Windows) ===" -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot" -ForegroundColor White

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
& $venvPython -m pip install -e "${BackendDir}[dev]" pyinstaller --quiet
Write-Host "  Done" -ForegroundColor Green

# 4. Run lint
Write-Host "`n[4/8] Running lint..." -ForegroundColor Yellow
& $venvPython -m ruff check "$BackendDir\app" "$BackendDir\tests" --quiet
Write-Host "  Lint passed" -ForegroundColor Green

# 5. Run backend tests
Write-Host "`n[5/8] Running backend tests..." -ForegroundColor Yellow
Set-Location $BackendDir
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

# 7. Build frontend
Write-Host "`n[7/8] Building frontend..." -ForegroundColor Yellow
Set-Location $FrontendDir
npm ci --silent
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
& (Join-Path $FrontendDir "node_modules\.bin\tauri.cmd") build --bundles nsis --config "src-tauri/tauri.sidecar.conf.json"
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [error] Tauri build failed" -ForegroundColor Red
    exit 1
}

# Copy installer to dist
$tauriTarget = Join-Path $TauriDir "target\release"
$installerSource = Get-ChildItem "$tauriTarget\bundle\nsis\*.exe" | Select-Object -First 1
if ($installerSource) {
    New-Item -ItemType Directory -Force -Path (Join-Path $DistDir "windows") | Out-Null
    Copy-Item $installerSource.FullName (Join-Path $DistDir "windows\") -Force
    Write-Host "  Installer: $($installerSource.Name)" -ForegroundColor Green
}

# Generate SHA-256
$artifacts = Get-ChildItem (Join-Path $DistDir "windows\") -Filter "*.exe"
foreach ($artifact in $artifacts) {
    $hash = Get-FileHash $artifact.FullName -Algorithm SHA256
    "$($hash.Hash)  $($artifact.Name)" | Out-File "$($artifact.FullName).sha256" -Encoding ascii
    Write-Host "  SHA256 ($($artifact.Name)): $($hash.Hash)" -ForegroundColor Green
}

Write-Host "`n=== Build complete! ===" -ForegroundColor Cyan
Write-Host "Installer: $DistDir\windows\" -ForegroundColor White
Set-Location $ProjectRoot
