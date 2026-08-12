# OIHK Basic — Development script (Windows)
# Starts both backend and frontend servers.

param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

$ErrorActionPreference = "Stop"
$RootDir = Split-Path $PSScriptRoot -Parent
$jobs = @()

if ($BackendOnly -and $FrontendOnly) {
    throw "Choose either -BackendOnly or -FrontendOnly, not both."
}

Write-Host "=== OIHK Basic Development ===" -ForegroundColor Cyan

if (-not $FrontendOnly) {
    $backendDir = Join-Path $RootDir "backend"
    $pythonCandidates = @(
        (Join-Path $backendDir ".venv\Scripts\python.exe"),
        (Join-Path $backendDir "venv\Scripts\python.exe")
    )
    $pythonPath = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $pythonPath) {
        $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
        if (-not $pythonCommand) {
            throw "Python was not found. Create backend\.venv and install backend dependencies first."
        }
        $pythonPath = $pythonCommand.Source
    }

    Write-Host "Starting backend (http://127.0.0.1:8000)..." -ForegroundColor Green
    $backendJob = Start-Job -ScriptBlock {
        param($dir, $python)
        Set-Location $dir
        & $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
        if ($LASTEXITCODE -ne 0) { throw "Backend exited with code $LASTEXITCODE." }
    } -ArgumentList $backendDir, $pythonPath
    $jobs += $backendJob
}

if (-not $BackendOnly) {
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "npm was not found. Install Node.js 22 and run npm ci in frontend first."
    }
    Write-Host "Starting frontend (http://127.0.0.1:5173)..." -ForegroundColor Green
    $frontendJob = Start-Job -ScriptBlock {
        param($dir)
        Set-Location $dir
        npm run dev
        if ($LASTEXITCODE -ne 0) { throw "Frontend exited with code $LASTEXITCODE." }
    } -ArgumentList (Join-Path $RootDir "frontend")
    $jobs += $frontendJob
}

Write-Host ""
Write-Host "Servers starting..." -ForegroundColor Yellow
Write-Host "  Backend:  http://127.0.0.1:8000" -ForegroundColor White
Write-Host "  API Docs: http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "  Frontend: http://127.0.0.1:5173" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop all servers." -ForegroundColor Yellow

# Stream both jobs. If either server exits, stop the other one and surface the failure.
try {
    while ($true) {
        Receive-Job -Job $jobs -ErrorAction Continue
        $finished = $jobs | Where-Object { $_.State -in @("Completed", "Failed", "Stopped") }
        if ($finished) { break }
        Start-Sleep -Milliseconds 250
    }
    Receive-Job -Job $jobs -ErrorAction Continue
    $failed = $jobs | Where-Object { $_.State -eq "Failed" } | Select-Object -First 1
    if ($failed) {
        $reason = $failed.ChildJobs[0].JobStateInfo.Reason
        if ($reason) { throw $reason.Message }
        throw "A development server failed."
    }
    throw "A development server stopped. Review the output above."
} finally {
    Write-Host "Shutting down..." -ForegroundColor Yellow
    Stop-Job -Job $jobs -ErrorAction SilentlyContinue
    Remove-Job -Job $jobs -Force -ErrorAction SilentlyContinue
}
