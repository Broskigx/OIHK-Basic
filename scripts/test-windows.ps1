#!/usr/bin/env pwsh
# OIHK Basic - Windows Test Script

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent

# 1. Backend tests
Write-Host "=== Backend Tests ===" -ForegroundColor Cyan
$venvDir = Join-Path $ProjectRoot "backend\venv"
if (Test-Path $venvDir) {
    & (Join-Path $venvDir "Scripts\Activate.ps1")
}

Set-Location (Join-Path $ProjectRoot "backend")
pip install -e "." --quiet
pip install pytest pytest-asyncio httpx --quiet

Write-Host "Running pytest..." -ForegroundColor Yellow
pytest --verbose --tb=short --no-header -x
if ($LASTEXITCODE -ne 0) {
    Write-Host "[error] Backend tests failed" -ForegroundColor Red
    exit 1
}
Write-Host "[ok] Backend tests passed" -ForegroundColor Green

# 2. Frontend tests
Write-Host "`n=== Frontend Tests ===" -ForegroundColor Cyan
Set-Location (Join-Path $ProjectRoot "frontend")
npm install --silent

if (Test-Path "package.json") {
    if (Select-String -Path "package.json" -Pattern '"test"' -Quiet) {
        npm test
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[error] Frontend tests failed" -ForegroundColor Red
            exit 1
        }
        Write-Host "[ok] Frontend tests passed" -ForegroundColor Green
    } else {
        Write-Host "No test script found in package.json, skipping" -ForegroundColor Yellow
    }
}

# 3. Import isolation check
Write-Host "`n=== Import Isolation Check ===" -ForegroundColor Cyan
$issues = @()
# Check that no Basic files import from outside OIHK-Basic
Get-ChildItem -Path $ProjectRoot -Recurse -Filter "*.py" | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    if ($content -match 'from\s+\.\.(?!\.)') {
        $issues += "  Import issue in $($_.Name)"
    }
}
if ($issues.Count -gt 0) {
    Write-Host "[error] Import isolation issues found:" -ForegroundColor Red
    $issues | ForEach-Object { Write-Host $_ }
    exit 1
}
Write-Host "[ok] All imports are isolated" -ForegroundColor Green

Set-Location $ProjectRoot
Write-Host "`n=== All tests passed! ===" -ForegroundColor Cyan
