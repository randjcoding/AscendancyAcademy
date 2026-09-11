"""Create missing tables/columns so local sqlite and Rocky stay in sync."""
from __future__ import annotations

from sqlalchemy import inspect, text

from app.database import Base, engine


def _add_if_missing(table: str, cols: set[str], name: str, ddl: str, adds: list[str]) -> None:
    if name not in cols:
        adds.append(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    adds: list[str] = []
    dialect = engine.dialect.name
    bool_true = "TRUE" if dialect == "postgresql" else "1"

    if "assignments" in tables:
        cols = {c["name"] for c in insp.get_columns("assignments")}
        _add_if_missing(cols=cols, table="assignments", name="book_id", ddl="book_id INTEGER", adds=adds)
        _add_if_missing(cols=cols, table="assignments", name="pages", ddl="pages VARCHAR(80) DEFAULT ''", adds=adds)
        _add_if_missing(cols=cols, table="assignments", name="page_start", ddl="page_start INTEGER", adds=adds)
        _add_if_missing(
            cols=cols,
            table="assignments",
            name="has_work",
            ddl=f"has_work BOOLEAN DEFAULT {bool_true}",
            adds=adds,
        )

    if "books" in tables:
        cols = {c["name"] for c in insp.get_columns("books")}
        _add_if_missing(cols=cols, table="books", name="kind", ddl="kind VARCHAR(20) DEFAULT 'other'", adds=adds)
        _add_if_missing(cols=cols, table="books", name="isbn", ddl="isbn VARCHAR(32) DEFAULT ''", adds=adds)
        _add_if_missing(cols=cols, table="books", name="upc", ddl="upc VARCHAR(32) DEFAULT ''", adds=adds)

    if "users" in tables:
        cols = {c["name"] for c in insp.get_columns("users")}
        _add_if_missing(
            cols=cols,
            table="users",
            name="density_preference",
            ddl="density_preference VARCHAR(20) DEFAULT 'cozy'",
            adds=adds,
        )

    if not adds:
        return
    with engine.begin() as conn:
        for stmt in adds:
            conn.execute(text(stmt))
