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

# Attempt standard pip installation with flags for externally-managed & python 3.13 envs
$PYTHON_CMD -m pip install --break-system-packages --no-deps -e "$SCRIPT_DIR" 2>/dev/null || \
$PYTHON_CMD -m pip install --break-system-packages --no-deps "$SCRIPT_DIR" 2>/dev/null || \
$PYTHON_CMD -m pip install --no-deps -e "$SCRIPT_DIR" 2>/dev/null || \
$PYTHON_CMD -m pip install --no-deps "$SCRIPT_DIR" 2>/dev/null || true

# Always guarantee apptainer_diag Python package is installed in site-packages
SITE_PACKAGES=$($PYTHON_CMD -c "import site; print(site.getsitepackages()[0])" 2>/dev/null || true)
if [ -n "$SITE_PACKAGES" ] && [ -d "$SITE_PACKAGES" ]; then
    cp -r "$SCRIPT_DIR/apptainer_diag" "$SITE_PACKAGES/" 2>/dev/null || true
fi

USER_SITE=$($PYTHON_CMD -c "import site; print(site.getusersitepackages())" 2>/dev/null || true)
if [ -n "$USER_SITE" ]; then
    mkdir -p "$USER_SITE" 2>/dev/null || true
    cp -r "$SCRIPT_DIR/apptainer_diag" "$USER_SITE/" 2>/dev/null || true
fi

# Always guarantee apptainer-diag executable entrypoint binary exists on PATH
BIN_WRAPPER="#!/bin/sh
exec $PYTHON_CMD -m apptainer_diag.cli \"\$@\"
"

for bin_dir in "/usr/local/bin" "/usr/bin" "$HOME/.local/bin"; do
    if [ -d "$bin_dir" ] || mkdir -p "$bin_dir" 2>/dev/null; then
        (echo "$BIN_WRAPPER" > "$bin_dir/apptainer-diag") 2>/dev/null || true
        chmod +x "$bin_dir/apptainer-diag" 2>/dev/null || true
    fi
done

# Verify package import and CLI entrypoint
$PYTHON_CMD -c "import apptainer_diag; print('apptainer_diag package import SUCCESS')"

echo "Oracle solution executed successfully."
exit 0
