#!/usr/bin/env pwsh
param(
    [Parameter(Mandatory = $true)]
    [string]$SidecarPath
)

$ErrorActionPreference = "Stop"
$resolvedSidecar = (Resolve-Path -LiteralPath $SidecarPath).Path
if (-not $resolvedSidecar.EndsWith(".exe", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "The sidecar smoke test requires a packaged Windows executable."
}
$smokeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("oihk-sidecar-smoke-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $smokeRoot | Out-Null
$database = Join-Path $smokeRoot "oihk-basic.db"
$smokeAppData = Join-Path $smokeRoot "AppData"
$projectRoot = Split-Path $PSScriptRoot -Parent
$productVersion = (Get-Content (Join-Path $projectRoot "VERSION") -Raw).Trim()
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$listener.Start()
$port = ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
$listener.Stop()

$previousDatabase = $env:OIHK_DATABASE_URL
$previousStorage = $env:OIHK_STORAGE_DIR
$previousEnvironment = $env:OIHK_ENVIRONMENT
$previousAuth = $env:OIHK_AUTH_ENABLED
$previousPackaged = $env:OIHK_DESKTOP_PACKAGED
$previousAppData = $env:APPDATA
try {
    $env:OIHK_DATABASE_URL = "sqlite+aiosqlite:///ambient-value-must-be-ignored.db"
    $env:OIHK_STORAGE_DIR = "ambient-value-must-be-ignored"
    $env:OIHK_ENVIRONMENT = "desktop"
    $env:OIHK_AUTH_ENABLED = "false"
    $env:OIHK_DESKTOP_PACKAGED = "1"
    $env:APPDATA = $smokeAppData
    $process = Start-Process -FilePath $resolvedSidecar -ArgumentList @(
        "--port", $port,
        "--data-dir", $smokeRoot
    ) -PassThru -WindowStyle Hidden
    $healthy = $false
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        if ($process.HasExited) { break }
        try {
            $response = Invoke-RestMethod -Uri "http://127.0.0.1:$port/health" -TimeoutSec 1
            if ($response.status -eq "ok") {
                $healthy = $true
                break
            }
        } catch {
            Start-Sleep -Milliseconds 250
        }
    }
    if (-not $healthy) {
        throw "The packaged sidecar did not expose a healthy loopback API."
    }
    if (-not (Test-Path -LiteralPath $database)) {
        throw "The packaged sidecar did not create its SQLite database."
    }
    $prepared = Invoke-RestMethod `
        -Uri "http://127.0.0.1:$port/updates/prepare" `
        -Method Post `
        -ContentType "application/json" `
        -Body (@{ target_version = $productVersion; channel = "alpha" } | ConvertTo-Json -Compress) `
        -TimeoutSec 40
    if (-not $prepared.update_token -or -not (Test-Path -LiteralPath $prepared.backup_path)) {
        throw "The packaged sidecar did not create its mandatory pre-update backup."
    }
    $backupMetadataPath = [System.IO.Path]::ChangeExtension($prepared.backup_path, ".metadata.json")
    if (-not (Test-Path -LiteralPath $backupMetadataPath)) {
        throw "The packaged sidecar did not persist backup metadata."
    }
    $backupMetadata = Get-Content -LiteralPath $backupMetadataPath -Raw | ConvertFrom-Json
    $backupHash = (Get-FileHash -LiteralPath $prepared.backup_path -Algorithm SHA256).Hash
    if (
        $backupHash -ne $prepared.backup_sha256.ToUpperInvariant() -or
        $backupHash -ne $backupMetadata.sha256.ToUpperInvariant() -or
        $backupMetadata.integrity_check -ne "ok" -or
        $backupMetadata.target_version -ne $productVersion
    ) {
        throw "The packaged sidecar backup metadata or SHA-256 is inconsistent."
    }
    Invoke-RestMethod `
        -Uri "http://127.0.0.1:$port/updates/shutdown" `
        -Method Post `
        -Headers @{ "X-OIHK-Update-Token" = $prepared.update_token } `
        -ContentType "application/json" `
        -Body '{}' `
        -TimeoutSec 5 | Out-Null
    for ($shutdownAttempt = 0; $shutdownAttempt -lt 80; $shutdownAttempt++) {
        $remaining = Get-CimInstance Win32_Process | Where-Object {
            $_.ExecutablePath -and
            [System.IO.Path]::GetFullPath($_.ExecutablePath).Equals(
                $resolvedSidecar,
                [System.StringComparison]::OrdinalIgnoreCase
            ) -and
            $_.CommandLine -like "*--port $port*"
        }
        if (-not $remaining) { break }
        Start-Sleep -Milliseconds 250
    }
    if ($remaining) {
        throw "The packaged sidecar did not stop gracefully after update preparation."
    }
} finally {
    $sidecarProcesses = Get-CimInstance Win32_Process | Where-Object {
        $_.ExecutablePath -and
        [System.IO.Path]::GetFullPath($_.ExecutablePath).Equals($resolvedSidecar, [System.StringComparison]::OrdinalIgnoreCase) -and
        $_.CommandLine -like "*--port $port*"
    }
    foreach ($sidecarProcess in $sidecarProcesses) {
        Stop-Process -Id $sidecarProcess.ProcessId -Force -ErrorAction SilentlyContinue
        Wait-Process -Id $sidecarProcess.ProcessId -ErrorAction SilentlyContinue
    }
    $env:OIHK_DATABASE_URL = $previousDatabase
    $env:OIHK_STORAGE_DIR = $previousStorage
    $env:OIHK_ENVIRONMENT = $previousEnvironment
    $env:OIHK_AUTH_ENABLED = $previousAuth
    $env:OIHK_DESKTOP_PACKAGED = $previousPackaged
    $env:APPDATA = $previousAppData
    $resolvedSmoke = [System.IO.Path]::GetFullPath($smokeRoot)
    $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    if ($resolvedSmoke.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path $resolvedSmoke -Leaf).StartsWith("oihk-sidecar-smoke-")) {
        for ($cleanupAttempt = 0; $cleanupAttempt -lt 20; $cleanupAttempt++) {
            try {
                Remove-Item -LiteralPath $resolvedSmoke -Recurse -Force
                break
            } catch {
                if ($cleanupAttempt -eq 19) { throw }
                Start-Sleep -Milliseconds 250
            }
        }
    }
}
Write-Host "  Packaged sidecar smoke test passed without a Python runtime." -ForegroundColor Green
