"""Books per class and page assignments."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "books" not in tables:
        op.create_table(
            "books",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("course_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("author", sa.String(length=160), nullable=False, server_default=""),
            sa.Column("notes", sa.Text(), nullable=False, server_default=""),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_books_course_id", "books", ["course_id"])
    cols = {c["name"] for c in insp.get_columns("assignments")}
    if "book_id" not in cols:
        op.add_column("assignments", sa.Column("book_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_assignments_book_id",
            "assignments",
            "books",
            ["book_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_assignments_book_id", "assignments", ["book_id"])
    if "pages" not in cols:
        op.add_column(
            "assignments",
            sa.Column("pages", sa.String(length=80), nullable=False, server_default=""),
        )
    if "page_start" not in cols:
        op.add_column("assignments", sa.Column("page_start", sa.Integer(), nullable=True))
    if "has_work" not in cols:
        op.add_column(
            "assignments",
            sa.Column("has_work", sa.Boolean(), nullable=False, server_default=sa.true()),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("assignments")}
    if "book_id" in cols:
        try:
            op.drop_index("ix_assignments_book_id", table_name="assignments")
        except Exception:
            pass
        try:
            op.drop_constraint("fk_assignments_book_id", "assignments", type_="foreignkey")
        except Exception:
            pass
        op.drop_column("assignments", "book_id")
    if "has_work" in cols:
        op.drop_column("assignments", "has_work")
    if "page_start" in cols:
        op.drop_column("assignments", "page_start")
    if "pages" in cols:
        op.drop_column("assignments", "pages")
    if "books" in set(insp.get_table_names()):
        op.drop_index("ix_books_course_id", table_name="books")
        op.drop_table("books")
