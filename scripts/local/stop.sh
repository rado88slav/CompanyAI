#!/usr/bin/env bash
# Description: Stop the CompanyAI Local Edition runtime without deleting data.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/local/common.sh
source "$SCRIPT_DIR/common.sh"

print_header "Stop"
require_local_runtime

cd "$PROJECT_ROOT"

compose stop

echo
echo "Stopped. Persistent Docker volumes were not removed."
