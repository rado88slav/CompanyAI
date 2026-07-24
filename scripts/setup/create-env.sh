#!/usr/bin/env bash
# Description: Create a secure local .env file with generated passwords and keys.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

ENV_EXAMPLE="$PROJECT_ROOT/.env.example"
ENV_FILE="$PROJECT_ROOT/.env"

FORCE=false

show_usage() {
    echo "Usage: $0 [--force]"
    echo
    echo "  --force   Replace an existing .env file."
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)
            FORCE=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            echo "Error: Unknown argument: $1" >&2
            show_usage >&2
            exit 1
            ;;
    esac
done

echo "======================================"
echo " Company AI - Create Environment"
echo "======================================"

if [[ ! -f "$ENV_EXAMPLE" ]]; then
    echo "Error: Missing environment template:" >&2
    echo "$ENV_EXAMPLE" >&2
    exit 1
fi

if ! command -v openssl >/dev/null 2>&1; then
    echo "Error: OpenSSL is required to generate secure secrets." >&2
    exit 1
fi

if [[ -f "$ENV_FILE" && "$FORCE" != true ]]; then
    echo
    echo "The local .env file already exists."
    echo "No changes were made."
    echo
    echo "To replace it intentionally, run:"
    echo "$0 --force"
    exit 0
fi

if command -v git >/dev/null 2>&1 &&
    git -C "$PROJECT_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then

    if ! git -C "$PROJECT_ROOT" check-ignore -q .env; then
        echo "Error: .env is not ignored by Git." >&2
        echo "Refusing to create a file containing secrets." >&2
        exit 1
    fi
fi

generate_aes_key() {
    openssl rand -base64 32 |
        tr '+/' '-_' |
        tr -d '\n'
}

POSTGRES_PASSWORD="$(openssl rand -hex 24)"
APP_SECRET_KEY="$(openssl rand -hex 32)"
AGENT_CREDENTIAL_PEPPER="$(openssl rand -hex 32)"
AGENT_JWT_SECRET="$(openssl rand -hex 32)"
ENCRYPTION_ACTIVE_KEY_ID="local-primary"
ENCRYPTION_KEY_MATERIAL="$(generate_aes_key)"
ENCRYPTION_KEYRING_JSON="{\"$ENCRYPTION_ACTIVE_KEY_ID\":\"$ENCRYPTION_KEY_MATERIAL\"}"

umask 077

temporary_file="$(mktemp "$PROJECT_ROOT/.env.tmp.XXXXXX")"

cleanup() {
    rm -f "$temporary_file"
}

trap cleanup EXIT

awk \
    -v postgres_password="$POSTGRES_PASSWORD" \
    -v app_secret_key="$APP_SECRET_KEY" \
    -v agent_credential_pepper="$AGENT_CREDENTIAL_PEPPER" \
    -v agent_jwt_secret="$AGENT_JWT_SECRET" \
    -v encryption_key_id="$ENCRYPTION_ACTIVE_KEY_ID" \
    -v encryption_keyring="$ENCRYPTION_KEYRING_JSON" '
        /^POSTGRES_PASSWORD=/ {
            print "POSTGRES_PASSWORD=" postgres_password
            next
        }

        /^APP_SECRET_KEY=/ {
            print "APP_SECRET_KEY=" app_secret_key
            next
        }

        /^AGENT_CREDENTIAL_PEPPER=/ {
            print "AGENT_CREDENTIAL_PEPPER=" agent_credential_pepper
            next
        }

        /^AGENT_JWT_SECRET=/ {
            print "AGENT_JWT_SECRET=" agent_jwt_secret
            next
        }

        /^CREDENTIAL_ENCRYPTION_ACTIVE_KEY_ID=/ {
            print "CREDENTIAL_ENCRYPTION_ACTIVE_KEY_ID=" encryption_key_id
            next
        }

        /^CREDENTIAL_ENCRYPTION_KEYRING=/ {
            print "CREDENTIAL_ENCRYPTION_KEYRING=" encryption_keyring
            next
        }

        {
            print
        }
    ' "$ENV_EXAMPLE" > "$temporary_file"

if grep -q 'replace_with_generated_' "$temporary_file"; then
    echo "Error: One or more secret placeholders were not replaced." >&2
    exit 1
fi

chmod 600 "$temporary_file"
mv "$temporary_file" "$ENV_FILE"

trap - EXIT

echo
echo "Local environment file created successfully:"
echo "- File: .env"
echo "- Permissions: owner read/write only"
echo "- Secrets: generated securely"
echo
echo "Secret values were not printed to the terminal."
