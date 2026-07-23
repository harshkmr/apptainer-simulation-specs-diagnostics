#!/bin/bash
set -uo pipefail

# Determine writeable log directory for verifier output
VERIFIER_LOG_DIR="/logs/verifier"
if mkdir -p "$VERIFIER_LOG_DIR" 2>/dev/null && touch "$VERIFIER_LOG_DIR/.test_write" 2>/dev/null; then
    rm -f "$VERIFIER_LOG_DIR/.test_write" 2>/dev/null || true
else
    VERIFIER_LOG_DIR="/tmp/logs/verifier"
    mkdir -p "$VERIFIER_LOG_DIR" 2>/dev/null || true
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Install solution package
pip install --no-deps -e "$BASE_DIR/solution" &>/dev/null || true

# Run pytest across all test files in tests/ directory
PYTHONPATH="$BASE_DIR/solution:$BASE_DIR:${PYTHONPATH:-}" python3 -m pytest \
  --ctrf "$VERIFIER_LOG_DIR/ctrf.json" "$SCRIPT_DIR" -rA
RC=$?

# Write reward file to writeable log directory
if [ "$RC" -eq 0 ]; then
    echo 1 > "$VERIFIER_LOG_DIR/reward.txt" 2>/dev/null || true
else
    echo 0 > "$VERIFIER_LOG_DIR/reward.txt" 2>/dev/null || true
fi

if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
