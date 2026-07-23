#!/bin/bash
set -uo pipefail

VERIFIER_LOG_DIR="/logs/verifier"
if [ -d "/logs" ] && [ -w "/logs" ]; then
    mkdir -p "$VERIFIER_LOG_DIR" 2>/dev/null || VERIFIER_LOG_DIR="/tmp/logs/verifier"
else
    VERIFIER_LOG_DIR="/tmp/logs/verifier"
fi
mkdir -p "$VERIFIER_LOG_DIR"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Run pytest unit tests pre-installed in Docker environment
PYTHONPATH="$BASE_DIR/solution:$BASE_DIR:${PYTHONPATH:-}" python3 -m pytest \
  --ctrf "$VERIFIER_LOG_DIR/ctrf.json" "$SCRIPT_DIR/test_outputs.py" -rA

if [ $? -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
