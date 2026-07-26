#!/usr/bin/env bash
# Description: Build and start the CompanyAI Local Edition runtime.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/local/common.sh
source "$SCRIPT_DIR/common.sh"

print_header "Start"
require_local_runtime

cd "$PROJECT_ROOT"

echo "Validating local Compose configuration..."
compose config --quiet

echo "Starting local runtime..."
compose up -d --build --wait --wait-timeout 120

echo
compose ps

echo
echo "CompanyAI is available at http://localhost:8080"
