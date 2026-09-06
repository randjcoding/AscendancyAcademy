"""Provision Postgres role + database for Ascendancy Academy.

Run on the Rocky server (or from a machine that can reach Postgres as admin):

    export PG_ADMIN_PASSWORD='postgres-superuser-password'
    export AA_DB_PASSWORD='strong-app-password'
    python scripts/setup_postgres.py

Idempotent — safe to run multiple times. Never commit passwords.
"""
from __future__ import annotations

import os
import sys

import psycopg
from psycopg import sql

DB_NAME = os.environ.get("AA_DB_NAME", "aa")
DB_USER = os.environ.get("AA_DB_USER", "aa")
DB_PASSWORD = os.environ.get("AA_DB_PASSWORD")
PG_HOST = os.environ.get("PG_HOST", "localhost")
PG_PORT = int(os.environ.get("PG_PORT", "5432"))
PG_ADMIN_USER = os.environ.get("PG_ADMIN_USER", "postgres")
PG_ADMIN_PASSWORD = os.environ.get("PG_ADMIN_PASSWORD")


def main() -> None:
    if not PG_ADMIN_PASSWORD:
        print("ERROR: set PG_ADMIN_PASSWORD (postgres superuser password).", file=sys.stderr)
        sys.exit(2)
    if not DB_PASSWORD:
        print("ERROR: set AA_DB_PASSWORD (password for the aa login role).", file=sys.stderr)
        sys.exit(2)

    print(f"Connecting to {PG_HOST}:{PG_PORT} as {PG_ADMIN_USER}...")
    with psycopg.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_ADMIN_USER,
        password=PG_ADMIN_PASSWORD,
        dbname="postgres",
        autocommit=True,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = %s", (DB_USER,))
            if cur.fetchone() is None:
                print(f"Creating role {DB_USER}...")
                cur.execute(
                    sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD %s").format(sql.Identifier(DB_USER)),
                    (DB_PASSWORD,),
                )
            else:
                print(f"Role {DB_USER} exists — updating password.")
                cur.execute(
                    sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD %s").format(sql.Identifier(DB_USER)),
                    (DB_PASSWORD,),
                )

            cur.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (DB_NAME,))
            if cur.fetchone() is None:
                print(f"Creating database {DB_NAME}...")
                cur.execute(
                    sql.SQL("CREATE DATABASE {} OWNER {} ENCODING 'UTF8'").format(
                        sql.Identifier(DB_NAME), sql.Identifier(DB_USER)
                    )
                )
            else:
                print(f"Database {DB_NAME} already exists.")

            cur.execute(
                sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                    sql.Identifier(DB_NAME), sql.Identifier(DB_USER)
                )
            )

    with psycopg.connect(
        host=PG_HOST,
        port=PG_PORT,
        user=PG_ADMIN_USER,
        password=PG_ADMIN_PASSWORD,
        dbname=DB_NAME,
        autocommit=True,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("GRANT ALL ON SCHEMA public TO {}").format(sql.Identifier(DB_USER))
            )
            cur.execute(
                sql.SQL("ALTER SCHEMA public OWNER TO {}").format(sql.Identifier(DB_USER))
            )
            cur.execute(
                sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {}").format(
                    sql.Identifier(DB_USER)
                )
            )
            cur.execute(
                sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {}").format(
                    sql.Identifier(DB_USER)
                )
            )

    print()
    print("Postgres setup complete.")
    print(f"DATABASE_URL=postgresql+psycopg://{DB_USER}:<password>@{PG_HOST}:{PG_PORT}/{DB_NAME}")
    print()
    print("On Rocky, use localhost in DATABASE_URL:")
    print(f"DATABASE_URL=postgresql+psycopg://{DB_USER}:<password>@localhost:5432/{DB_NAME}")


if __name__ == "__main__":
    main()
