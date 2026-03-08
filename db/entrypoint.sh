#!/bin/sh
set -euo pipefail

echo "=== Schema migration (dry-run) ==="
psqldef \
  --host="$DATABASE_HOST" \
  --port="${DATABASE_PORT:-5432}" \
  --user="$DATABASE_USER" \
  --password="$DATABASE_PASSWORD" \
  "$DATABASE_NAME" \
  --dry-run \
  < /migration/schema_postgres.sql

echo "=== Schema migration (apply) ==="
psqldef \
  --host="$DATABASE_HOST" \
  --port="${DATABASE_PORT:-5432}" \
  --user="$DATABASE_USER" \
  --password="$DATABASE_PASSWORD" \
  "$DATABASE_NAME" \
  < /migration/schema_postgres.sql

echo "=== IAM grants ==="
PGPASSWORD="$DATABASE_PASSWORD" psql \
  -h "$DATABASE_HOST" \
  -p "${DATABASE_PORT:-5432}" \
  -U "$DATABASE_USER" \
  -d "$DATABASE_NAME" \
  -f /migration/grant_iam.sql

echo "=== Migration complete ==="
