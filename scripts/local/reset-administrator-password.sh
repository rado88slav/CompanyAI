#!/usr/bin/env bash
# Description: Interactively reset one existing local administrator password.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/local/common.sh
source "$SCRIPT_DIR/common.sh"

print_header "Reset Administrator Password"
require_local_runtime

cd "$PROJECT_ROOT"

compose exec backend python -m app.cli.reset_administrator_password
