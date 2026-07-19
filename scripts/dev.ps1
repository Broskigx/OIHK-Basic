# OIHK Basic — Development script (Windows)
# Starts both backend and frontend servers.

param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

$ErrorActionPreference = "Stop"
$RootDir = Split-Path $PSScriptRoot -Parent

Write-Host "=== OIHK Basic Development ===" -ForegroundColor Cyan

if (-not $FrontendOnly) {
    Write-Host "Starting backend (http://127.0.0.1:8000)..." -ForegroundColor Green
    $backendJob = Start-Job -ScriptBlock {
        param($dir)
        Set-Location $dir
        # Try to use virtual environment if it exists
        $venvActivate = Join-Path $dir "venv\Scripts\Activate.ps1"
        if (Test-Path $venvActivate) {
            & $venvActivate
        }
        uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
    } -ArgumentList (Join-Path $RootDir "backend")
}

if (-not $BackendOnly) {
    Write-Host "Starting frontend (http://127.0.0.1:5173)..." -ForegroundColor Green
    $frontendJob = Start-Job -ScriptBlock {
        param($dir)
        Set-Location $dir
        npm run dev
    } -ArgumentList (Join-Path $RootDir "frontend")
}

Write-Host ""
Write-Host "Servers starting..." -ForegroundColor Yellow
Write-Host "  Backend:  http://127.0.0.1:8000" -ForegroundColor White
Write-Host "  API Docs: http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "  Frontend: http://127.0.0.1:5173" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop all servers." -ForegroundColor Yellow

# Wait for jobs and handle Ctrl+C
try {
    Receive-Job -Job $backendJob -Wait -AutoRemoveJob -ErrorAction SilentlyContinue
    if (-not $BackendOnly) {
        Receive-Job -Job $frontendJob -Wait -AutoRemoveJob -ErrorAction SilentlyContinue
    }
} catch {
    Write-Host "Shutting down..." -ForegroundColor Yellow
    Stop-Job -Job $backendJob -ErrorAction SilentlyContinue
    if (-not $BackendOnly) {
        Stop-Job -Job $frontendJob -ErrorAction SilentlyContinue
    }
}
