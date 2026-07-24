#!/usr/bin/env bash
# Description: Validate create-env.sh safely in an isolated temporary project.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

test_root="$(mktemp -d /tmp/company-ai-create-env-test.XXXXXX)"
cleanup() {
    rm -rf "$test_root"
}
trap cleanup EXIT

mkdir -p "$test_root/scripts/setup"
cp "$PROJECT_ROOT/.env.example" "$test_root/.env.example"
cp "$PROJECT_ROOT/scripts/setup/create-env.sh" \
    "$test_root/scripts/setup/create-env.sh"
chmod 700 "$test_root/scripts/setup/create-env.sh"

first_output="$test_root/first-output.txt"
"$test_root/scripts/setup/create-env.sh" >"$first_output"

python - "$test_root/.env" "$first_output" <<'PY'
import base64
import json
from pathlib import Path
import stat
import sys

env_path = Path(sys.argv[1])
output_path = Path(sys.argv[2])
values = {}
for line in env_path.read_text(encoding="utf-8").splitlines():
    if line and not line.startswith("#") and "=" in line:
        name, value = line.split("=", 1)
        values[name] = value

assert "CREDENTIAL_ENCRYPTION_KEY" not in values
assert values["CREDENTIAL_ENCRYPTION_ACTIVE_KEY_ID"] == "local-primary"
raw_keyring = values["CREDENTIAL_ENCRYPTION_KEYRING"]
keyring = json.loads(raw_keyring)
assert set(keyring) == {"local-primary"}
encoded_key = keyring["local-primary"]
decoded_key = base64.b64decode(
    encoded_key.encode("ascii"),
    altchars=b"-_",
    validate=True,
)
assert len(decoded_key) == 32
assert encoded_key not in output_path.read_text(encoding="utf-8")
assert stat.S_IMODE(env_path.stat().st_mode) == 0o600
PY

first_checksum="$(sha256sum "$test_root/.env" | awk '{print $1}')"
second_output="$test_root/second-output.txt"
"$test_root/scripts/setup/create-env.sh" >"$second_output"
second_checksum="$(sha256sum "$test_root/.env" | awk '{print $1}')"

[[ "$first_checksum" == "$second_checksum" ]]
[[ "$(<"$second_output")" == *"No changes were made."* ]]

"$test_root/scripts/setup/create-env.sh" --force \
    >"$test_root/force-output.txt"
[[ "$(stat -c '%a' "$test_root/.env")" == "600" ]]

python - "$test_root/.env" <<'PY'
import base64
import json
from pathlib import Path
import sys

values = {}
for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    if line and not line.startswith("#") and "=" in line:
        name, value = line.split("=", 1)
        values[name] = value

keyring = json.loads(values["CREDENTIAL_ENCRYPTION_KEYRING"])
assert len(base64.b64decode(
    keyring[values["CREDENTIAL_ENCRYPTION_ACTIVE_KEY_ID"]].encode("ascii"),
    altchars=b"-_",
    validate=True,
)) == 32
PY

echo "create-env isolated tests: passed"
