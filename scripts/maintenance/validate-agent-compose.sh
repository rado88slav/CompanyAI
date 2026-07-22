#!/usr/bin/env bash
# Description: Validate tracked Agent Authentication Docker Compose propagation without resolving secrets.

set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"
GENERATOR_FILE="${PROJECT_ROOT}/scripts/setup/add-agent-identity.sh"
PATCH_FILE="$(mktemp)"

cleanup() {
    rm -f "${PATCH_FILE}"
}
trap cleanup EXIT

VARIABLES=(
    AGENT_CREDENTIAL_PEPPER
    AGENT_JWT_SECRET
    AGENT_JWT_ALGORITHM
    AGENT_JWT_TTL_SECONDS
    AGENT_JWT_ISSUER
    AGENT_JWT_AUDIENCE
)

for variable_name in "${VARIABLES[@]}"; do
    expected="      ${variable_name}: \${${variable_name}}"
    if [[ "$(grep -Fxc "${expected}" "${COMPOSE_FILE}")" -ne 1 ]]; then
        printf 'ERROR: backend Compose mapping is missing or duplicated for %s.\n' "${variable_name}" >&2
        exit 1
    fi
done

sed -n "/^base64 -d <<'AGENT_IDENTITY_PATCH'/,/^AGENT_IDENTITY_PATCH$/p" "${GENERATOR_FILE}" \
    | sed '1d;$d' \
    | base64 -d \
    | gzip -d > "${PATCH_FILE}"

if ! grep -Fq 'diff --git a/docker-compose.yml b/docker-compose.yml' "${PATCH_FILE}"; then
    printf '%s\n' 'ERROR: Agent Identity generator does not manage docker-compose.yml.' >&2
    exit 1
fi

for variable_name in "${VARIABLES[@]}"; do
    expected="+      ${variable_name}: \${${variable_name}}"
    if [[ "$(grep -Fxc "${expected}" "${PATCH_FILE}")" -ne 1 ]]; then
        printf 'ERROR: generator Compose mapping is missing or duplicated for %s.\n' "${variable_name}" >&2
        exit 1
    fi
done

printf '%s\n' 'Agent Authentication Compose placeholder validation passed.'
