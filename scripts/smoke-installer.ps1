param(
    [Parameter(Mandatory = $true)]
    [string]$InstallerPath
)

$ErrorActionPreference = "Stop"
$installer = (Resolve-Path -LiteralPath $InstallerPath).Path
$smokeRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("oihk-installer-smoke-" + [Guid]::NewGuid().ToString("N"))
$installDir = Join-Path $smokeRoot "installed"
$smokeAppData = Join-Path $smokeRoot "AppData"
$previousAppData = $env:APPDATA
$previousLocalAppData = $env:LOCALAPPDATA
$previousPath = $env:PATH
$desktopPath = Join-Path $installDir "oihk-basic-desktop.exe"
$sidecarPath = Join-Path $installDir "oihk-basic-backend.exe"
$uninstallerPath = Join-Path $installDir "uninstall.exe"
$activeRuntime = $null
$evidenceStoragePath = ""

function Start-InstalledRuntime([string]$Desktop, [string]$Sidecar) {
    $desktopProcess = Start-Process -FilePath $Desktop -PassThru -WindowStyle Hidden
    $port = 0
    for ($attempt = 0; $attempt -lt 160; $attempt++) {
        if ($desktopProcess.HasExited) { break }
        $managed = Get-CimInstance Win32_Process | Where-Object {
            $_.ExecutablePath -and
            [System.IO.Path]::GetFullPath($_.ExecutablePath).Equals(
                [System.IO.Path]::GetFullPath($Sidecar),
                [System.StringComparison]::OrdinalIgnoreCase
            ) -and
            $_.CommandLine -match '--port\s+(?<port>\d+)'
        } | Select-Object -First 1
        if ($managed -and $managed.CommandLine -match '--port\s+(?<port>\d+)') {
            $port = [int]$Matches.port
            try {
                $health = Invoke-RestMethod -Uri "http://127.0.0.1:$port/health" -TimeoutSec 1
                if ($health.status -eq "ok") {
                    return [pscustomobject]@{ Desktop = $desktopProcess; Port = $port }
                }
            } catch {
                # The packaged service may still be applying migrations.
            }
        }
        Start-Sleep -Milliseconds 250
    }
    throw "The installed application did not start a healthy managed sidecar."
}

function Stop-InstalledRuntime($Runtime, [string]$Sidecar) {
    if (-not $Runtime.Desktop.CloseMainWindow()) {
        throw "The installed application did not accept a normal window close."
    }
    if (-not $Runtime.Desktop.WaitForExit(15000)) {
        throw "The installed application did not exit after a normal window close."
    }
    Start-Sleep -Milliseconds 500
    $orphan = Get-CimInstance Win32_Process | Where-Object {
        $_.ExecutablePath -and
        [System.IO.Path]::GetFullPath($_.ExecutablePath).Equals(
            [System.IO.Path]::GetFullPath($Sidecar),
            [System.StringComparison]::OrdinalIgnoreCase
        ) -and
        $_.CommandLine -match "--port\s+$($Runtime.Port)(?:\s|$)"
    }
    if ($orphan) {
        throw "The installed managed sidecar remained after a normal desktop close."
    }
}

function Invoke-JsonPost([string]$Uri, $Body) {
    return Invoke-RestMethod `
        -Uri $Uri `
        -Method Post `
        -ContentType "application/json" `
        -Body ($Body | ConvertTo-Json -Depth 8 -Compress) `
        -TimeoutSec 15
}

try {
    New-Item -ItemType Directory -Path $smokeRoot | Out-Null
    $install = Start-Process `
        -FilePath $installer `
        -ArgumentList @("/S", "/D=$installDir") `
        -PassThru `
        -Wait `
        -WindowStyle Hidden
    if ($install.ExitCode -ne 0) {
        throw "The NSIS installer exited with code $($install.ExitCode)."
    }
    foreach ($required in @($desktopPath, $sidecarPath, $uninstallerPath)) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
            throw "The NSIS installation is incomplete: $required"
        }
    }
    $forbidden = Get-ChildItem -LiteralPath $installDir -Recurse -Force | Where-Object {
        $_.Name -in @(".env", ".git", "node_modules", "venv") -or
        $_.Extension -in @(".key", ".pem")
    }
    if ($forbidden) {
        throw "The installer contains forbidden development or secret material: $($forbidden.FullName -join ', ')"
    }

    $env:APPDATA = $smokeAppData
    $env:LOCALAPPDATA = $smokeAppData
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    $activeRuntime = Start-InstalledRuntime $desktopPath $sidecarPath
    $api = "http://127.0.0.1:$($activeRuntime.Port)"

    $case = Invoke-JsonPost "$api/cases" @{
        title = "Installed smoke case"
        summary = "Created by the clean installer validation."
        legal_basis = "Authorized release validation"
        scope_statement = "Local packaged application persistence validation only"
        priority = "normal"
        tags = @("installer-smoke")
        notes = "Must survive restart and uninstall."
    }
    $first = Invoke-JsonPost "$api/graph/entities" @{
        case_id = $case.id
        label = "example.com"
        type = "url"
        confidence = 0.8
        relation_label = "analyst_linked"
    }
    $null = Invoke-JsonPost "$api/graph/entities" @{
        case_id = $case.id
        label = "support@example.com"
        type = "email"
        confidence = 0.75
        connect_to_id = $first.id
        relation_label = "contact"
    }
    $null = Invoke-JsonPost "$api/sources/text" @{
        case_id = $case.id
        title = "Installed smoke source"
        body = "Authorized local evidence note for example.com"
        citation = "installer-smoke"
        license = "case-note"
        reliability = 0.9
    }
    $null = Invoke-JsonPost "$api/reports/$($case.id)/generate" @{
        title = "Installed smoke report"
        format = "markdown"
        sections = @("investigation", "entities", "relationships", "sources", "evidence", "limitations")
        limitations = "Synthetic release validation data."
    }

    $evidenceFile = Join-Path $smokeRoot "evidence.txt"
    [System.IO.File]::WriteAllText($evidenceFile, "OIHK Basic packaged evidence smoke test.")
    $curl = Join-Path $env:SystemRoot "System32\curl.exe"
    $evidenceJson = & $curl --silent --show-error --fail `
        -F "case_id=$($case.id)" `
        -F "notes=Installer smoke evidence" `
        -F "tags=installer-smoke" `
        -F "file=@$evidenceFile;type=text/plain" `
        "$api/evidence"
    if ($LASTEXITCODE -ne 0) {
        throw "The installed application could not ingest evidence."
    }
    $evidence = $evidenceJson | ConvertFrom-Json
    $storage = Invoke-RestMethod -Uri "$api/settings/storage" -TimeoutSec 10
    $evidenceStoragePath = $storage.storage_path
    $expectedDataRoot = [System.IO.Path]::GetFullPath((Join-Path $smokeAppData "OIHK-Basic"))
    $actualDatabase = [System.IO.Path]::GetFullPath($storage.database_path)
    if (-not $actualDatabase.StartsWith($expectedDataRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "The installed database was created outside the managed application-data directory."
    }

    Stop-InstalledRuntime $activeRuntime $sidecarPath
    $activeRuntime = $null

    $activeRuntime = Start-InstalledRuntime $desktopPath $sidecarPath
    $api = "http://127.0.0.1:$($activeRuntime.Port)"
    $cases = @(Invoke-RestMethod -Uri "$api/cases" -TimeoutSec 10)
    $graph = Invoke-RestMethod -Uri "$api/graph/$($case.id)" -TimeoutSec 10
    $reports = @(Invoke-RestMethod -Uri "$api/reports/case/$($case.id)" -TimeoutSec 10)
    $evidenceItems = @(Invoke-RestMethod -Uri "$api/evidence/$($case.id)" -TimeoutSec 10)
    $custody = Invoke-RestMethod -Uri "$api/custody/$($case.id)" -TimeoutSec 10
    $verification = Invoke-JsonPost "$api/evidence/items/$($evidence.id)/verify" @{}
    if (
        $cases.Count -ne 1 -or
        $graph.nodes.Count -lt 2 -or
        $graph.edges.Count -lt 1 -or
        $reports.Count -lt 1 -or
        $evidenceItems.Count -lt 1 -or
        -not $custody.intact -or
        -not $verification.intact
    ) {
        $brokenEntries = @($custody.entries | Where-Object { -not $_.ok }) |
            Select-Object sequence, source_title, content_ok, seal_ok, chain_ok, signature_ok
        throw (
            "Installed data did not survive restart: cases=$($cases.Count), " +
            "nodes=$($graph.nodes.Count), edges=$($graph.edges.Count), reports=$($reports.Count), " +
            "evidence=$($evidenceItems.Count), custody=$($custody.intact), verify=$($verification.intact), " +
            "broken=$($brokenEntries | ConvertTo-Json -Compress)."
        )
    }
    Stop-InstalledRuntime $activeRuntime $sidecarPath
    $activeRuntime = $null

    $uninstall = Start-Process `
        -FilePath $uninstallerPath `
        -ArgumentList "/S" `
        -PassThru `
        -Wait `
        -WindowStyle Hidden
    if ($uninstall.ExitCode -ne 0) {
        throw "The NSIS uninstaller exited with code $($uninstall.ExitCode)."
    }
    for ($attempt = 0; $attempt -lt 40 -and (Test-Path -LiteralPath $desktopPath); $attempt++) {
        Start-Sleep -Milliseconds 250
    }
    if ((Test-Path -LiteralPath $desktopPath) -or (Test-Path -LiteralPath $sidecarPath)) {
        throw "The NSIS uninstaller left application binaries behind."
    }
    $databaseAfterUninstall = Join-Path $expectedDataRoot "oihk-basic.db"
    if (-not (Test-Path -LiteralPath $databaseAfterUninstall -PathType Leaf)) {
        throw "The NSIS uninstaller removed the user's SQLite database."
    }
    if (-not (Test-Path -LiteralPath $evidenceStoragePath -PathType Container)) {
        throw "The NSIS uninstaller removed the user's managed evidence directory."
    }
} finally {
    if ($activeRuntime) {
        Stop-Process -Id $activeRuntime.Desktop.Id -Force -ErrorAction SilentlyContinue
        Wait-Process -Id $activeRuntime.Desktop.Id -ErrorAction SilentlyContinue
    }
    $managedProcesses = Get-CimInstance Win32_Process | Where-Object {
        $_.ExecutablePath -and (
            [System.IO.Path]::GetFullPath($_.ExecutablePath).Equals(
                [System.IO.Path]::GetFullPath($desktopPath),
                [System.StringComparison]::OrdinalIgnoreCase
            ) -or
            [System.IO.Path]::GetFullPath($_.ExecutablePath).Equals(
                [System.IO.Path]::GetFullPath($sidecarPath),
                [System.StringComparison]::OrdinalIgnoreCase
            )
        )
    }
    foreach ($candidate in $managedProcesses) {
        Stop-Process -Id $candidate.ProcessId -Force -ErrorAction SilentlyContinue
        Wait-Process -Id $candidate.ProcessId -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $uninstallerPath -PathType Leaf) {
        $cleanupUninstall = Start-Process `
            -FilePath $uninstallerPath `
            -ArgumentList "/S" `
            -PassThru `
            -Wait `
            -WindowStyle Hidden
        if ($cleanupUninstall.ExitCode -ne 0) {
            Write-Warning "Cleanup uninstaller exited with code $($cleanupUninstall.ExitCode)."
        }
    }
    $env:APPDATA = $previousAppData
    $env:LOCALAPPDATA = $previousLocalAppData
    $env:PATH = $previousPath
    $resolvedSmoke = [System.IO.Path]::GetFullPath($smokeRoot)
    $tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    if ($resolvedSmoke.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase) -and
        (Split-Path $resolvedSmoke -Leaf).StartsWith("oihk-installer-smoke-")) {
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

Write-Host "  Clean NSIS install, restart, persistence, custody, and uninstall smoke test passed." -ForegroundColor Green
