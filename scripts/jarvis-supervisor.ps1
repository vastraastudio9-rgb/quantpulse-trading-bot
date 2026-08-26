param(
    [string]$WorkspaceRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$PythonPath = $env:JARVIS_PYTHON,
    [string]$NodePath = $env:JARVIS_NODE,
    [int]$IntervalSeconds = 30
)

$ErrorActionPreference = "Stop"
$workspace = [System.IO.Path]::GetFullPath($WorkspaceRoot)
$engineMain = Join-Path $workspace "mini-services\trading-engine\main.py"
$dashboardServer = Join-Path $workspace ".next\standalone\server.js"
$safeRestart = Join-Path $workspace "scripts\restart-engine-safe.ps1"
$logPath = Join-Path $workspace "jarvis-supervisor.log"
$engineOut = Join-Path $workspace "engine.out.log"
$engineErr = Join-Path $workspace "engine.err.log"
$dashboardOut = Join-Path $workspace "dashboard.out.log"
$dashboardErr = Join-Path $workspace "dashboard.err.log"
$IntervalSeconds = [Math]::Max(10, [Math]::Min(300, $IntervalSeconds))

if (-not $PythonPath) { $PythonPath = (Get-Command python -ErrorAction Stop).Source }
if (-not $NodePath) { $NodePath = (Get-Command node -ErrorAction Stop).Source }
foreach ($path in @($engineMain, $dashboardServer, $safeRestart, $PythonPath, $NodePath)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Required runtime artifact missing: $path" }
}

$created = $false
$mutex = [System.Threading.Mutex]::new($true, "QuantPulseJarvisSupervisor", [ref]$created)
if (-not $created) { throw "JARVIS supervisor is already running." }

function Write-SupervisorEvent([string]$level, [string]$message) {
    $event = @{ timestamp = [DateTimeOffset]::UtcNow.ToString("o"); level = $level; message = $message }
    Add-Content -LiteralPath $logPath -Value ($event | ConvertTo-Json -Compress)
}

function Test-Endpoint([string]$uri) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $uri -TimeoutSec 5
        return $response.StatusCode -eq 200
    } catch { return $false }
}

try {
    Write-SupervisorEvent "INFO" "Supervisor started"
    while ($true) {
        if (-not (Test-Endpoint "http://127.0.0.1:3030/health")) {
            $listener = Get-NetTCPConnection -LocalPort 3030 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($listener) {
                Write-SupervisorEvent "ERROR" "Engine health failed but port 3030 is occupied; recovery blocked"
            } else {
                Start-Process -FilePath $PythonPath -ArgumentList @($engineMain) -WorkingDirectory (Split-Path $engineMain) `
                    -RedirectStandardOutput $engineOut -RedirectStandardError $engineErr -WindowStyle Hidden
                Write-SupervisorEvent "WARNING" "Engine process recovered from persisted PAPER state"
            }
        } else {
            try {
                $release = Invoke-RestMethod -Uri "http://127.0.0.1:3030/api/jarvis/release-status" -TimeoutSec 5
                if ($release.restart_required -and $release.preflight.safe_to_restart) {
                    & $safeRestart -WorkspaceRoot $workspace -PythonPath $PythonPath | Out-Null
                    Write-SupervisorEvent "INFO" "Pending verified engine release activated after flat-paper preflight"
                }
            } catch {
                Write-SupervisorEvent "ERROR" ("Deferred release check failed safely: " + $_.Exception.Message)
            }
        }
        if (-not (Test-Endpoint "http://127.0.0.1:3000/")) {
            $listener = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($listener) {
                Write-SupervisorEvent "ERROR" "Dashboard health failed but port 3000 is occupied; recovery blocked"
            } else {
                $env:PORT = "3000"
                $env:HOSTNAME = "127.0.0.1"
                Start-Process -FilePath $NodePath -ArgumentList @($dashboardServer) -WorkingDirectory $workspace `
                    -RedirectStandardOutput $dashboardOut -RedirectStandardError $dashboardErr -WindowStyle Hidden
                Write-SupervisorEvent "WARNING" "Production dashboard process recovered"
            }
        }
        Start-Sleep -Seconds $IntervalSeconds
    }
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
