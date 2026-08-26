param(
    [string]$WorkspaceRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$PythonPath = $env:JARVIS_PYTHON
)

$ErrorActionPreference = "Stop"
$workspace = [System.IO.Path]::GetFullPath($WorkspaceRoot)
$engineDirectory = Join-Path $workspace "mini-services\trading-engine"
$mainPath = Join-Path $engineDirectory "main.py"
if (-not $PythonPath) {
    $venvPython = Join-Path $workspace ".venv\Scripts\python.exe"
    $PythonPath = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { (Get-Command python -ErrorAction Stop).Source }
}
$PythonPath = [System.IO.Path]::GetFullPath($PythonPath)
if (-not (Test-Path -LiteralPath $mainPath) -or -not (Test-Path -LiteralPath $PythonPath)) {
    throw "Engine or Python runtime not found."
}

$release = $null
try {
    $release = Invoke-RestMethod -Uri "http://127.0.0.1:3030/api/jarvis/release-status" -TimeoutSec 10
} catch {
    if ($_.Exception.Response.StatusCode.value__ -ne 404) { throw }
}
if ($release) {
    if (-not $release.preflight.safe_to_restart) {
        throw ("Restart blocked: " + ($release.preflight.blockers -join "; "))
    }
} else {
    # Legacy engines predate release-status. Preserve fail-closed behavior by
    # independently verifying PAPER mode and a flat portfolio before upgrade.
    $mode = Invoke-RestMethod -Uri "http://127.0.0.1:3030/api/trading/mode" -TimeoutSec 10
    $positions = Invoke-RestMethod -Uri "http://127.0.0.1:3030/api/positions" -TimeoutSec 10
    if ($mode.mode -ne "PAPER") { throw "Legacy restart blocked: trading mode is not PAPER." }
    if (@($positions).Count -ne 0) { throw "Legacy restart blocked: paper portfolio is not flat." }
}

$listener = Get-NetTCPConnection -LocalPort 3030 -State Listen | Select-Object -First 1
if (-not $listener) { throw "No trading engine is listening on port 3030." }
$process = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)"
$expected = [System.IO.Path]::GetFullPath($mainPath)
if (-not $process.CommandLine -or -not $process.CommandLine.Contains($expected)) {
    throw "Port 3030 process does not match the expected workspace engine."
}

Stop-Process -Id $listener.OwningProcess -ErrorAction Stop
$stdout = Join-Path $workspace "engine.out.log"
$stderr = Join-Path $workspace "engine.err.log"
$started = Start-Process -FilePath $PythonPath -ArgumentList @($mainPath) -WorkingDirectory $engineDirectory `
    -RedirectStandardOutput $stdout -RedirectStandardError $stderr -WindowStyle Hidden -PassThru

$deadline = (Get-Date).AddSeconds(20)
do {
    Start-Sleep -Milliseconds 500
    try { $health = Invoke-RestMethod -Uri "http://127.0.0.1:3030/health" -TimeoutSec 2 } catch { $health = $null }
} while (-not $health -and (Get-Date) -lt $deadline)

if (-not $health) {
    throw "Engine restart failed health verification. New process ID: $($started.Id)"
}
$health | ConvertTo-Json -Depth 5
