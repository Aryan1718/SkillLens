#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   SUPABASE_DB_URL='postgresql://...' ./scripts/db_apply.sh
#   SUPABASE_DB_URL='postgresql://...' ./scripts/db_apply.sh supabase/migrations/20260216170000_init_skilllens.sql
#   SUPABASE_DB_URL='postgresql://...' ./scripts/db_apply.sh database/02_artifacts_and_jobs.sql

# Load repo .env automatically if present.
if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "Error: psql is not installed or not in PATH." >&2
  exit 1
fi

if [[ -z "${SUPABASE_DB_URL:-}" ]]; then
  echo "Error: SUPABASE_DB_URL is required." >&2
  echo "Example: export SUPABASE_DB_URL='postgresql://postgres:<PASSWORD>@db.<PROJECT-REF>.supabase.co:5432/postgres?sslmode=require'" >&2
  exit 1
fi

apply_file() {
  local sql_file="$1"
  if [[ ! -f "$sql_file" ]]; then
    echo "Error: migration file not found: $sql_file" >&2
    exit 1
  fi

  echo "Applying migration: $sql_file"
  psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f "$sql_file"
}

if [[ $# -gt 0 ]]; then
  apply_file "$1"
  echo "Done."
  exit 0
fi

shopt -s nullglob
migration_files=(supabase/migrations/*.sql database/*.sql)
shopt -u nullglob

if [[ ${#migration_files[@]} -eq 0 ]]; then
  echo "No migrations found in supabase/migrations/ or database/." >&2
  exit 1
fi

IFS=$'\n' sorted_files=($(printf '%s\n' "${migration_files[@]}" | sort))
unset IFS

for file in "${sorted_files[@]}"; do
  apply_file "$file"
done

echo "All migrations applied successfully."
