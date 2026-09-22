#!/usr/bin/env bash

set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL is required}"

for command in pg_dump pg_restore psql createdb dropdb; do
  command -v "$command" >/dev/null || {
    echo "Required PostgreSQL client command is missing: $command" >&2
    exit 1
  }
done

source_major="$(psql "$DATABASE_URL" -Atqc "show server_version_num" | cut -c1-2)"
client_major="$(pg_dump --version | sed -E 's/.* ([0-9]+).*/\1/')"
if [[ "$source_major" != "$client_major" ]]; then
  echo "pg_dump major $client_major must match PostgreSQL server major $source_major" >&2
  exit 1
fi

run_component="${GITHUB_RUN_ID:-local}"
run_component="${run_component//[^0-9]/}"
target_db="fde_restore_${run_component:-0}_$RANDOM"
if [[ ! "$target_db" =~ ^fde_restore_[0-9]+_[0-9]+$ ]]; then
  echo "Refusing unsafe disposable database name" >&2
  exit 1
fi

readarray -t urls < <(
  python - "$DATABASE_URL" "$target_db" <<'PY'
import sys
from sqlalchemy.engine import make_url

source = make_url(sys.argv[1])
print(source.set(database="postgres").render_as_string(hide_password=False))
print(source.set(database=sys.argv[2]).render_as_string(hide_password=False))
PY
)
admin_url="${urls[0]}"
target_url="${urls[1]}"

source_db="$(psql "$DATABASE_URL" -Atqc "select current_database()")"
if [[ "$source_db" == "$target_db" ]]; then
  echo "Disposable database must differ from source" >&2
  exit 1
fi

work_dir="$(mktemp -d)"
backup_file="$work_dir/application.dump"
cleanup() {
  dropdb --maintenance-db="$admin_url" --if-exists --force "$target_db" >/dev/null 2>&1 || true
  temp_root="${TMPDIR:-/tmp}"
  if [[ -n "$work_dir" && -d "$work_dir" && "$work_dir" == "$temp_root/"* ]]; then
    rm -rf -- "$work_dir"
  else
    echo "Refusing to remove unexpected temporary path: $work_dir" >&2
  fi
}
trap cleanup EXIT

# Ensure the restored database contains a deterministic non-PII evidence row.
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 <<'SQL' >/dev/null
INSERT INTO "user" (id, email, hashed_password, role, is_active, must_change_password, token_version)
VALUES ('00000000-0000-4000-8000-000000000099', 'backup-evidence@example.com', 'not-a-login-hash', 'viewer', false, true, 0)
ON CONFLICT (email) DO NOTHING;
SQL

pg_dump --format=custom --no-owner --no-acl --file="$backup_file" "$DATABASE_URL"
createdb --maintenance-db="$admin_url" "$target_db"
pg_restore --exit-on-error --no-owner --no-acl --dbname="$target_url" "$backup_file"

tables=(user import_batch validation_row contact job job_attempt job_outbox audit_event alembic_version)
for table in "${tables[@]}"; do
  quoted_table="\"$table\""
  source_count="$(psql "$DATABASE_URL" -Atqc "select count(*) from $quoted_table")"
  restored_count="$(psql "$target_url" -Atqc "select count(*) from $quoted_table")"
  if [[ "$source_count" != "$restored_count" ]]; then
    echo "Count mismatch for $table: source=$source_count restored=$restored_count" >&2
    exit 1
  fi
done

integrity_failures="$(psql "$target_url" -Atqc "
select
  (select count(*) from validation_row r left join import_batch i on i.id=r.import_id where i.id is null) +
  (select count(*) from contact c left join import_batch i on i.id=c.source_import_id where i.id is null) +
  (select count(*) from job j left join import_batch i on i.id=j.import_id where i.id is null) +
  (select count(*) from job_attempt a left join job j on j.id=a.job_id where j.id is null) +
  (select count(*) from job_outbox o left join job j on j.id=o.job_id where j.id is null) +
  (select count(*) from audit_event a left join \"user\" u on u.id=a.actor_id where a.actor_id is not null and u.id is null) +
  (select count(*) from (select normalized_email from contact group by normalized_email having count(*) > 1) duplicates)
")"
if [[ "$integrity_failures" != "0" ]]; then
  echo "Restored database integrity checks failed: $integrity_failures" >&2
  exit 1
fi

marker="$(psql "$target_url" -Atqc "select count(*) from \"user\" where email='backup-evidence@example.com' and is_active=false")"
if [[ "$marker" != "1" ]]; then
  echo "Restored evidence row is missing" >&2
  exit 1
fi

echo "Backup restore verified in disposable database $target_db; source $source_db was not modified except for the disabled synthetic evidence user."
