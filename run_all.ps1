# ==============================================================================
# StreamVault Master Test & Execution Script (Windows PowerShell)
# Executes all 8 project phases: tests, ETL pipeline, diagnosis, scaling benchmark,
# strategy CLI, visualization charts, and repository hygiene gates.
# ==============================================================================

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Resolve script root directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Detect Python interpreter
$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    $PythonCmd = Get-Command py -ErrorAction SilentlyContinue
}

if (-not $PythonCmd) {
    Write-Error "ERROR: Python is not installed or not found in PATH."
    exit 1
}

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "STREAMVAULT MASTER RUNNER (PowerShell: run_all.ps1)" -ForegroundColor Cyan
Write-Host "Using Python: $(& $PythonCmd.Source --version 2>&1)" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

# Execute unified Python orchestrator
& $PythonCmd.Source run_all.py $args
$ExitCode = $LASTEXITCODE

if ($ExitCode -ne 0) {
    Write-Host "`n[ERROR] StreamVault suite finished with errors (Exit Code $ExitCode)." -ForegroundColor Red
    exit $ExitCode
} else {
    Write-Host "`n[SUCCESS] Entire StreamVault suite completed successfully!" -ForegroundColor Green
    exit 0
}
