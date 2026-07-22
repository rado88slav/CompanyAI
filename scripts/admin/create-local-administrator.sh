#!/usr/bin/env bash
# Description: Create a local administrator without exposing the password in shell history.

set -Eeuo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${PROJECT_ROOT}"

printf '%s\n' "======================================"
printf '%s\n' " Company AI - Create Administrator"
printf '%s\n' "======================================"
printf '\n'

docker compose config --quiet
docker compose up -d --wait postgres

read -r -p "Administrator email: " administrator_email
read -r -p "Administrator full name: " administrator_full_name

printf '%s' "Password (minimum 12 characters): "
read -r -s administrator_password
printf '\n'

printf '%s' "Confirm password: "
read -r -s administrator_password_confirmation
printf '\n'

if [[ "${administrator_password}" != \
      "${administrator_password_confirmation}" ]]
then
    unset administrator_password
    unset administrator_password_confirmation

    printf '%s\n' "Error: Passwords do not match." >&2
    exit 1
fi

if (( ${#administrator_password} < 12 )); then
    unset administrator_password
    unset administrator_password_confirmation

    printf '%s\n' \
        "Error: Password must contain at least 12 characters." \
        >&2
    exit 1
fi

printf '\n%s\n' \
    "Creating the first local administrator as a superuser..."

printf '%s\n%s\n%s\n%s\n' \
    "${administrator_email}" \
    "${administrator_full_name}" \
    "${administrator_password}" \
    "true" \
| docker compose run --rm -T backend \
    python -m app.cli.create_administrator

unset administrator_password
unset administrator_password_confirmation

printf '\n%s\n' "Local administrator command completed."
