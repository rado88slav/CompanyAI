#!/usr/bin/env bash
# Description: Show CompanyAI Local Edition container and image status.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/local/common.sh
source "$SCRIPT_DIR/common.sh"

print_header "Status"
require_local_runtime

cd "$PROJECT_ROOT"

echo "Docker Engine:"
docker version --format 'Server version: {{.Server.Version}}'

echo
echo "Services:"
compose ps -a

echo
echo "Images:"
compose images

echo
echo "Persistent volumes:"
docker volume ls --filter name=company_ai_local
