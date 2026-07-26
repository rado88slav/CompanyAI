#!/usr/bin/env bash
# Description: Stop and remove CompanyAI Local Edition containers without deleting business data.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/local/common.sh
source "$SCRIPT_DIR/common.sh"

print_header "Uninstall Containers"
require_local_runtime

cd "$PROJECT_ROOT"

compose down --remove-orphans

echo
echo "Application containers were removed."
echo "Business data volumes were NOT deleted."
echo "To remove data, use an explicitly destructive manual Docker volume removal after verified backups."
