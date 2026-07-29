#!/usr/bin/env pwsh
param(
    [Parameter(Mandatory = $true)]
    [string]$DesktopPath
)

$ErrorActionPreference = "Stop"
$desktop = (Resolve-Path -LiteralPath $DesktopPath).Path
$desktopDirectory = Split-Path $desktop -Parent
$sidecar = Join-Path $desktopDirectory "oihk-basic-backend.exe"
if (-not (Test-Path -LiteralPath $sidecar)) {
    throw "The managed sidecar is not adjacent to the release desktop executable."
}
$smokeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("oihk-desktop-smoke-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $smokeRoot | Out-Null
$smokeAppData = Join-Path $smokeRoot "AppData"
$database = Join-Path $smokeAppData "OIHK-Basic\oihk-basic.db"
$previousAppData = $env:APPDATA

try {
    $env:APPDATA = $smokeAppData
    $desktopProcess = Start-Process -FilePath $desktop -PassThru -WindowStyle Hidden
    $port = 0
    $healthy = $false
    for ($attempt = 0; $attempt -lt 160; $attempt++) {
        if ($desktopProcess.HasExited) { break }
        $managed = Get-CimInstance Win32_Process | Where-Object {
            $_.ExecutablePath -and
            [System.IO.Path]::GetFullPath($_.ExecutablePath).Equals(
                [System.IO.Path]::GetFullPath($sidecar),
                [System.StringComparison]::OrdinalIgnoreCase
            ) -and
            $_.CommandLine -match '--port\s+(?<port>\d+)'
        } | Select-Object -First 1
        if ($managed -and $managed.CommandLine -match '--port\s+(?<port>\d+)') {
            $port = [int]$Matches.port
            try {
                $response = Invoke-RestMethod -Uri "http://127.0.0.1:$port/health" -TimeoutSec 1
                if ($response.status -eq "ok") {
                    $healthy = $true
                    break
                }
            } catch {
                # The managed sidecar may still be running migrations.
            }
        }
        Start-Sleep -Milliseconds 250
    }
    if (-not $healthy) {
        throw "The release desktop executable did not start a healthy managed sidecar."
    }
    $corsResponse = Invoke-WebRequest `
        -Uri "http://127.0.0.1:$port/health" `
        -Headers @{ Origin = "http://tauri.localhost" } `
        -UseBasicParsing `
        -TimeoutSec 2
    if ($corsResponse.Headers["Access-Control-Allow-Origin"] -ne "http://tauri.localhost") {
        throw "The packaged API does not authorize the Tauri webview origin."
    }
    if (-not (Test-Path -LiteralPath $database)) {
        throw "The desktop smoke did not create its isolated database."
    }
    if (-not $desktopProcess.CloseMainWindow()) {
        throw "The desktop smoke could not request a normal window close."
    }
    if (-not $desktopProcess.WaitForExit(15000)) {
        throw "The desktop process did not exit after a normal window close."
    }
    Start-Sleep -Milliseconds 500
    $orphan = Get-CimInstance Win32_Process | Where-Object {
        $_.ExecutablePath -and
        [System.IO.Path]::GetFullPath($_.ExecutablePath).Equals(
            [System.IO.Path]::GetFullPath($sidecar),
            [System.StringComparison]::OrdinalIgnoreCase
        ) -and
        $_.CommandLine -match "--port\s+$port(?:\s|$)"
    }
    if ($orphan) {
        throw "The managed sidecar remained after a normal desktop close."
    }
} finally {
    $desktopProcesses = Get-CimInstance Win32_Process | Where-Object {
        $_.ProcessId -eq $desktopProcess.Id -or
        ($port -gt 0 -and $_.ExecutablePath -and $_.CommandLine -like "*--port $port*" -and
            [System.IO.Path]::GetFullPath($_.ExecutablePath).Equals(
                [System.IO.Path]::GetFullPath($sidecar),
                [System.StringComparison]::OrdinalIgnoreCase
            )
        )
    }
    foreach ($candidate in $desktopProcesses) {
        Stop-Process -Id $candidate.ProcessId -Force -ErrorAction SilentlyContinue
        Wait-Process -Id $candidate.ProcessId -ErrorAction SilentlyContinue
    }
    $env:APPDATA = $previousAppData
    $resolvedSmoke = [System.IO.Path]::GetFullPath($smokeRoot)
    $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    if ($resolvedSmoke.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path $resolvedSmoke -Leaf).StartsWith("oihk-desktop-smoke-")) {
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
Write-Host "  Release desktop managed-sidecar smoke test passed." -ForegroundColor Green
