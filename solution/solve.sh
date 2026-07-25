#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect Python executable
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    PYTHON_CMD="python3"
fi

# Install package using pip with fallback flags for externally-managed environments (Python 3.13 / Debian)
$PYTHON_CMD -m pip install --break-system-packages --no-deps -e "$SCRIPT_DIR" 2>/dev/null || \
$PYTHON_CMD -m pip install --break-system-packages --no-deps "$SCRIPT_DIR" 2>/dev/null || \
$PYTHON_CMD -m pip install --no-deps -e "$SCRIPT_DIR" 2>/dev/null || \
$PYTHON_CMD -m pip install --no-deps "$SCRIPT_DIR" 2>/dev/null || \
$PYTHON_CMD -m pip install --user --no-deps "$SCRIPT_DIR" 2>/dev/null || true

# Ensure site-packages or user-site has apptainer_diag available
SITE_PACKAGES=$($PYTHON_CMD -c "import site; print(site.getsitepackages()[0])" 2>/dev/null || true)
if [ -n "$SITE_PACKAGES" ] && [ -d "$SITE_PACKAGES" ] && [ -w "$SITE_PACKAGES" ]; then
    cp -r "$SCRIPT_DIR/apptainer_diag" "$SITE_PACKAGES/" 2>/dev/null || true
fi

USER_SITE=$($PYTHON_CMD -c "import site; print(site.getusersitepackages())" 2>/dev/null || true)
if [ -n "$USER_SITE" ]; then
    mkdir -p "$USER_SITE" 2>/dev/null || true
    cp -r "$SCRIPT_DIR/apptainer_diag" "$USER_SITE/" 2>/dev/null || true
fi

# Verify installation and entrypoint
$PYTHON_CMD -c "import apptainer_diag; print('apptainer_diag imported successfully')"

echo "Oracle solution executed successfully."
exit 0
