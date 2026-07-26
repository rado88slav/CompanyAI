#!/usr/bin/env bash
# Description: Show sanitized local runtime logs from selected services.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/local/common.sh
source "$SCRIPT_DIR/common.sh"

print_header "Logs"
require_local_runtime

cd "$PROJECT_ROOT"

compose logs --tail "${COMPANYAI_LOG_LINES:-200}" "$@" \
    | sed -E 's/(Authorization: Bearer )[A-Za-z0-9._~+\/=-]+/\1[redacted]/g; s/(password=)[^ ]+/\1[redacted]/gi; s/(token=)[^ ]+/\1[redacted]/gi; s/(secret=)[^ ]+/\1[redacted]/gi'
