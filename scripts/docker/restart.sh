#!/usr/bin/env bash
# Description: Restart all Company AI Docker Compose services safely.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

STOP_SCRIPT="$SCRIPT_DIR/stop.sh"
START_SCRIPT="$SCRIPT_DIR/start.sh"

echo "======================================"
echo " Company AI - Restart"
echo "======================================"

if [[ ! -f "$STOP_SCRIPT" ]]; then
    echo "Error: Missing stop script: $STOP_SCRIPT" >&2
    exit 1
fi

if [[ ! -f "$START_SCRIPT" ]]; then
    echo "Error: Missing start script: $START_SCRIPT" >&2
    exit 1
fi

echo
echo "Stopping Company AI services..."
bash "$STOP_SCRIPT"

echo
echo "Starting Company AI services..."
bash "$START_SCRIPT"

echo
echo "Company AI restart completed successfully."