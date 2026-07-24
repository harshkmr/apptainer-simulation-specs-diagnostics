#!/bin/bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure log directory exists
mkdir -p /logs/verifier 2>/dev/null || true

# Run pytest against installed package / working environment without adding solution/ to PYTHONPATH
# This ensures NOP agent (which does not install solution) fails as expected.
python3 -m pytest --ctrf /logs/verifier/ctrf.json "$SCRIPT_DIR" -rA
RC=$?
if [ "$RC" -eq 0 ]; then
    echo 1 > /logs/verifier/reward.txt
else
    echo 0 > /logs/verifier/reward.txt
fi
