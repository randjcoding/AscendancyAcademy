"""Create missing tables/columns so local sqlite and Rocky stay in sync."""
from __future__ import annotations

from sqlalchemy import inspect, text

from app.database import Base, engine


def ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)
    insp = inspect(engine)
    if "assignments" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("assignments")}
    dialect = engine.dialect.name
    bool_true = "TRUE" if dialect == "postgresql" else "1"
    adds = []
    if "book_id" not in cols:
        adds.append("ALTER TABLE assignments ADD COLUMN book_id INTEGER")
    if "pages" not in cols:
        adds.append("ALTER TABLE assignments ADD COLUMN pages VARCHAR(80) DEFAULT ''")
    if "page_start" not in cols:
        adds.append("ALTER TABLE assignments ADD COLUMN page_start INTEGER")
    if "has_work" not in cols:
        adds.append(f"ALTER TABLE assignments ADD COLUMN has_work BOOLEAN DEFAULT {bool_true}")
    if not adds:
        return
    with engine.begin() as conn:
        for stmt in adds:
            conn.execute(text(stmt))
