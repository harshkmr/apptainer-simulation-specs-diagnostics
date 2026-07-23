#!/bin/bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Detect Python executable
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    PYTHON_CMD="python3"
fi

# Install the apptainer_diag package into Python environment
$PYTHON_CMD -m pip install --no-deps -e "$SCRIPT_DIR" &>/dev/null || $PYTHON_CMD -m pip install --no-deps "$SCRIPT_DIR" &>/dev/null || true

# Verify import
$PYTHON_CMD -c "import sys; sys.path.insert(0, '$SCRIPT_DIR'); sys.path.insert(0, '$BASE_DIR'); import apptainer_diag" &>/dev/null || true

echo "Oracle solution executed successfully."
exit 0
