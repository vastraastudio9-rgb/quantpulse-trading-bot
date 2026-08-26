param(
    [string]$WorkspaceRoot = (Split-Path -Parent $PSScriptRoot),
    [Parameter(Mandatory = $true)][string]$PythonPath,
    [Parameter(Mandatory = $true)][string]$NodePath
)

$ErrorActionPreference = "Stop"
$workspace = [System.IO.Path]::GetFullPath($WorkspaceRoot)
$supervisor = Join-Path $workspace "scripts\jarvis-supervisor.ps1"
foreach ($path in @($supervisor, $PythonPath, $NodePath)) {
    if (-not (Test-Path -LiteralPath $path)) { throw "Required path missing: $path" }
}
$powerShellPath = (Get-Process -Id $PID).Path
$arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$supervisor`" -WorkspaceRoot `"$workspace`" -PythonPath `"$PythonPath`" -NodePath `"$NodePath`""
$action = New-ScheduledTaskAction -Execute $powerShellPath -Argument $arguments
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName "QuantPulse-JARVIS-Supervisor" -Action $action -Trigger $trigger `
    -Settings $settings -Description "Keeps the PAPER-only QuantPulse engine and production dashboard healthy." `
    -Force | Out-Null
Start-ScheduledTask -TaskName "QuantPulse-JARVIS-Supervisor"
Get-ScheduledTask -TaskName "QuantPulse-JARVIS-Supervisor" | Select-Object TaskName, State
