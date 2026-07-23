#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$BASE_DIR"

# Step 1: Install the diagnostic analysis package
if [ -d "solution" ]; then
    pip install -e solution/ --break-system-packages 2>/dev/null || pip install -e solution/ || true
elif [ -f "setup.py" ]; then
    pip install -e . --break-system-packages 2>/dev/null || pip install -e . || true
fi

# Step 2: Verify package import and CLI entry point
python3 -c "import sys; sys.path.insert(0, '$SCRIPT_DIR'); sys.path.insert(0, '$BASE_DIR'); import apptainer_diag; print('apptainer_diag version:', apptainer_diag.__version__)"

echo "Apptainer diagnostics solution installed and verified."
