#!/usr/bin/env pwsh
# OIHK Basic — Windows Clean Script

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent

Write-Host "=== Cleaning OIHK Basic build artifacts ===" -ForegroundColor Yellow

$toRemove = @(
    "backend\venv",
    "backend\__pycache__",
    "backend\*.egg-info",
    "backend\*.db",
    "backend\storage",
    "frontend\node_modules",
    "frontend\dist",
    "frontend\.vite",
    "src-tauri\target",
    "build",
    "dist\sidecar",
    "*.db",
    "__pycache__"
)

foreach ($item in $toRemove) {
    $fullPath = Join-Path $ProjectRoot $item
    if (Test-Path $fullPath) {
        Write-Host "  Removing: $item"
        if (Test-Path $fullPath -PathType Container) {
            Remove-Item -Recurse -Force $fullPath -ErrorAction SilentlyContinue
        } else {
            Remove-Item -Force $fullPath -ErrorAction SilentlyContinue
        }
    }
}

Write-Host "`nClean complete. Project is ready for fresh build." -ForegroundColor Green
