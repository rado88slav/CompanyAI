#!/usr/bin/env bash
# Description: Restart the CompanyAI Local Edition runtime without deleting data.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/stop.sh"
echo
"$SCRIPT_DIR/start.sh"
