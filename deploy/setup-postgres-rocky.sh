#!/usr/bin/env bash
# Run ON Rocky (192.168.68.71) as joe — creates aa role + database.
#
#   export AA_DB_PASSWORD='your-strong-password'
#   bash deploy/setup-postgres-rocky.sh
#
# You will be prompted for the postgres superuser password unless
# PG_ADMIN_PASSWORD is already set in the environment.

set -euo pipefail

DB_NAME="${AA_DB_NAME:-aa}"
DB_USER="${AA_DB_USER:-aa}"
DB_PASSWORD="${AA_DB_PASSWORD:-}"

if [[ -z "${DB_PASSWORD}" ]]; then
  echo "ERROR: export AA_DB_PASSWORD before running." >&2
  exit 2
fi

echo "==> Creating role and database ${DB_NAME} / ${DB_USER}"

sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASSWORD}';
    RAISE NOTICE 'Created role ${DB_USER}';
  ELSE
    ALTER ROLE ${DB_USER} WITH LOGIN PASSWORD '${DB_PASSWORD}';
    RAISE NOTICE 'Updated password for ${DB_USER}';
  END IF;
END
\$\$;

SELECT 'CREATE DATABASE ${DB_NAME} OWNER ${DB_USER} ENCODING ''UTF8'''
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}')\gexec

GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
SQL

sudo -u postgres psql -v ON_ERROR_STOP=1 -d "${DB_NAME}" <<SQL
GRANT ALL ON SCHEMA public TO ${DB_USER};
ALTER SCHEMA public OWNER TO ${DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO ${DB_USER};
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO ${DB_USER};
SQL

echo ""
echo "[ok] Postgres ready."
echo "DATABASE_URL=postgresql+psycopg://${DB_USER}:<password>@localhost:5432/${DB_NAME}"
echo ""
echo "If local socket auth fails for the app, add to pg_hba.conf (before ident rules):"
echo "  # NOTE: this server uses password_encryption=md5, so rules must use md5 (not scram-sha-256)"
echo "  host    ${DB_NAME}    ${DB_USER}    127.0.0.1/32    md5"
echo "  host    ${DB_NAME}    ${DB_USER}    ::1/128         md5"
echo "Then: sudo systemctl reload postgresql"
