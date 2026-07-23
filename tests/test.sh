#!/bin/bash
set -uo pipefail

VERIFIER_LOG_DIR="/logs/verifier"
mkdir -p "$VERIFIER_LOG_DIR" 2>/dev/null || VERIFIER_LOG_DIR="/tmp/logs/verifier"
mkdir -p "$VERIFIER_LOG_DIR" 2>/dev/null || true

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Verify setuptools package installation & CLI entrypoint
pip install --no-deps -e "$BASE_DIR/solution" &>/dev/null || true

# Run pytest across all test files in tests/ directory
PYTHONPATH="$BASE_DIR/solution:$BASE_DIR:${PYTHONPATH:-}" python3 -m pytest \
  --ctrf "$VERIFIER_LOG_DIR/ctrf.json" "$SCRIPT_DIR" -rA

if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
