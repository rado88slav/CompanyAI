#!/usr/bin/env bash
# Description: Generate the project inventory and Bash scripts index.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ADMIN_DIR="$PROJECT_ROOT/project-admin"

INVENTORY_FILE="$ADMIN_DIR/inventory.md"
SCRIPTS_INDEX_FILE="$ADMIN_DIR/scripts-index.txt"

echo "======================================"
echo " Company AI - Update Inventory"
echo "======================================"

mkdir -p "$ADMIN_DIR"

inventory_tmp="$(mktemp "$ADMIN_DIR/.inventory.XXXXXX")"
scripts_tmp="$(mktemp "$ADMIN_DIR/.scripts-index.XXXXXX")"

cleanup() {
    rm -f "$inventory_tmp" "$scripts_tmp"
}

trap cleanup EXIT

replace_if_changed() {
    local temporary_file="$1"
    local destination_file="$2"

    if [[ -f "$destination_file" ]] && cmp -s "$temporary_file" "$destination_file"; then
        rm -f "$temporary_file"
        return
    fi

    mv "$temporary_file" "$destination_file"
}

project_name="$(basename "$PROJECT_ROOT")"

{
    echo "# Project Inventory"
    echo
    echo "Generated automatically by:"
    echo
    echo "\`scripts/maintenance/update-inventory.sh\`"
    echo
    echo "## Project"
    echo
    echo "- Name: \`$project_name\`"
    echo "- Repository root: detected automatically"
    echo
    echo "## Files"
    echo
    echo '```text'
    echo "."

    if command -v git >/dev/null 2>&1 &&
        git -C "$PROJECT_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then

        git -C "$PROJECT_ROOT" \
            ls-files --cached --others --exclude-standard |
            sort |
            sed 's#^#./#'
    else
        find "$PROJECT_ROOT" \
            -path "$PROJECT_ROOT/.git" -prune -o \
            -path "$PROJECT_ROOT/node_modules" -prune -o \
            -path "$PROJECT_ROOT/dashboard/node_modules" -prune -o \
            -path "$PROJECT_ROOT/.venv" -prune -o \
            -type f -print |
            sed "s#^$PROJECT_ROOT#.#" |
            sort
    fi

    echo '```'
} > "$inventory_tmp"

{
    echo "========================================="
    echo "Company AI - Scripts Index"
    echo "========================================="
    echo
    echo "Generated automatically."
    echo

    script_number=0

    while IFS= read -r script_path; do
        script_number=$((script_number + 1))
        relative_path="${script_path#"$PROJECT_ROOT/"}"

        if [[ -x "$script_path" ]]; then
            execution_status="executable"
        else
            execution_status="not executable"
        fi

        description="$(
            awk '
                /^# Description:/ {
                    sub(/^# Description:[[:space:]]*/, "")
                    print
                    exit
                }
            ' "$script_path"
        )"

        if [[ -z "$description" ]]; then
            description="No description yet"
        fi

        echo "$script_number. $relative_path"
        echo "   Description: $description"
        echo "   Status: $execution_status"
        echo
    done < <(
        find "$PROJECT_ROOT/scripts" \
            -type f \
            -name '*.sh' \
            -print |
            sort
    )

    if [[ "$script_number" -eq 0 ]]; then
        echo "No Bash scripts found."
    fi
} > "$scripts_tmp"

replace_if_changed "$inventory_tmp" "$INVENTORY_FILE"
replace_if_changed "$scripts_tmp" "$SCRIPTS_INDEX_FILE"

trap - EXIT

echo
echo "Project administration files updated:"
echo "- project-admin/inventory.md"
echo "- project-admin/scripts-index.txt"