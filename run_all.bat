@echo off
REM ============================================================================
REM StreamVault Master Test & Execution Batch Script (Windows CMD)
REM Executes all 8 project phases: tests, ETL pipeline, diagnosis, scaling benchmark,
REM strategy CLI, visualization charts, and repository hygiene gates.
REM ============================================================================

setlocal enabledelayedexpansion

echo ================================================================================
echo STREAMVAULT MASTER RUNNER (Batch Script: run_all.bat)
echo ================================================================================

python --version >nul 2>&1
if errorlevel 1 (
    py --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python is not installed or not in PATH.
        exit /b 1
    ) else (
        set PYTHON_BIN=py
    )
) else (
    set PYTHON_BIN=python
)

%PYTHON_BIN% run_all.py %*
exit /b %ERRORLEVEL%
