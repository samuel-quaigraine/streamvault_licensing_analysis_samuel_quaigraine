#!/usr/bin/env bash
# ==============================================================================
# StreamVault Master Test & Execution Shell Script (Linux / macOS / Git Bash)
# Executes all 8 project phases: tests, ETL pipeline, diagnosis, scaling benchmark,
# strategy CLI, visualization charts, and repository hygiene gates.
# ==============================================================================

set -e

# Determine project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Select Python executable
if command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo "ERROR: Python 3 is not installed or not in PATH." >&2
    exit 1
fi

echo "================================================================================"
echo "STREAMVAULT MASTER RUNNER (Shell Script: run_all.sh)"
echo "Using Python: $($PYTHON_BIN --version 2>&1)"
echo "================================================================================"

# Execute unified Python orchestrator
"$PYTHON_BIN" run_all.py "$@"
EXIT_CODE=$?

exit $EXIT_CODE
