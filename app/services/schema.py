"""Create missing tables/columns so local sqlite and Rocky stay in sync."""
from __future__ import annotations

from sqlalchemy import inspect, text

from app.database import Base, engine


def _add_if_missing(table: str, cols: set[str], name: str, ddl: str, adds: list[str]) -> None:
    if name not in cols:
        adds.append(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def _migrate_book_catalog(insp, dialect: str) -> None:
    tables = set(insp.get_table_names())
    if "books" not in tables or "course_books" not in tables:
        return
    book_cols = {c["name"] for c in insp.get_columns("books")}
    if "course_id" not in book_cols:
        return
    with engine.begin() as conn:
        if dialect == "postgresql":
            conn.execute(
                text(
                    """
                    INSERT INTO course_books (course_id, book_id, sort_order)
                    SELECT course_id, id, COALESCE(sort_order, 0)
                    FROM books
                    WHERE course_id IS NOT NULL
                    ON CONFLICT (course_id, book_id) DO NOTHING
                    """
                )
            )
            conn.execute(text("ALTER TABLE books DROP COLUMN IF EXISTS course_id"))
            if "sort_order" in book_cols:
                conn.execute(text("ALTER TABLE books DROP COLUMN IF EXISTS sort_order"))
        else:
            conn.execute(
                text(
                    """
                    INSERT OR IGNORE INTO course_books (course_id, book_id, sort_order)
                    SELECT course_id, id, COALESCE(sort_order, 0)
                    FROM books
                    WHERE course_id IS NOT NULL
                    """
                )
            )
            cols = [c["name"] for c in insp.get_columns("books") if c["name"] not in {"course_id", "sort_order"}]
            col_sql = ", ".join(cols)
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            conn.execute(
                text(
                    f"""
                    CREATE TABLE books__new (
                        id INTEGER PRIMARY KEY,
                        title VARCHAR(200) NOT NULL,
                        author VARCHAR(160) DEFAULT '',
                        notes TEXT DEFAULT '',
                        kind VARCHAR(20) DEFAULT 'other',
                        isbn VARCHAR(32) DEFAULT '',
                        upc VARCHAR(32) DEFAULT '',
                        created_at DATETIME
                    )
                    """
                )
            )
            conn.execute(text(f"INSERT INTO books__new ({col_sql}) SELECT {col_sql} FROM books"))
            conn.execute(text("DROP TABLE books"))
            conn.execute(text("ALTER TABLE books__new RENAME TO books"))
            conn.execute(text("PRAGMA foreign_keys=ON"))


def ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    adds: list[str] = []
    dialect = engine.dialect.name
    bool_true = "TRUE" if dialect == "postgresql" else "1"
    bool_false = "FALSE" if dialect == "postgresql" else "0"

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
        _add_if_missing(
            cols=cols,
            table="users",
            name="list_view_preference",
            ddl="list_view_preference VARCHAR(20) DEFAULT 'cards'",
            adds=adds,
        )
        _add_if_missing(
            cols=cols,
            table="users",
            name="role",
            ddl="role VARCHAR(20) DEFAULT 'teacher'",
            adds=adds,
        )

    if "tasks" in tables:
        cols = {c["name"] for c in insp.get_columns("tasks")}
        _add_if_missing(cols=cols, table="tasks", name="scope", ddl="scope VARCHAR(16) DEFAULT 'school'", adds=adds)
        _add_if_missing(cols=cols, table="tasks", name="owner_user_id", ddl="owner_user_id INTEGER", adds=adds)
        _add_if_missing(cols=cols, table="tasks", name="course_id", ddl="course_id INTEGER", adds=adds)
        _add_if_missing(cols=cols, table="tasks", name="priority", ddl="priority INTEGER DEFAULT 0", adds=adds)
        _add_if_missing(
            cols=cols,
            table="tasks",
            name="inbox",
            ddl=f"inbox BOOLEAN DEFAULT {bool_false}",
            adds=adds,
        )

    if "attendance_days" in tables:
        cols = {c["name"] for c in insp.get_columns("attendance_days")}
        _add_if_missing(
            cols=cols,
            table="attendance_days",
            name="locked",
            ddl=f"locked BOOLEAN DEFAULT {bool_false}",
            adds=adds,
        )
        if dialect == "postgresql":
            adds.append("ALTER TYPE attendance_status ADD VALUE IF NOT EXISTS 'sick'")

    if adds:
        with engine.begin() as conn:
            for stmt in adds:
                conn.execute(text(stmt))

    if "tasks" in tables:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE tasks SET owner_user_id = created_by_user_id WHERE owner_user_id IS NULL")
            )

    insp = inspect(engine)
    _migrate_book_catalog(insp, dialect)
