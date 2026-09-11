"""School book catalog, list view, sick, and attendance lock."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    dialect = bind.dialect.name

    if "users" in tables:
        user_cols = {c["name"] for c in insp.get_columns("users")}
        if "list_view_preference" not in user_cols:
            op.add_column(
                "users",
                sa.Column("list_view_preference", sa.String(length=20), server_default="cards"),
            )

    if "attendance_days" in tables:
        att_cols = {c["name"] for c in insp.get_columns("attendance_days")}
        if "locked" not in att_cols:
            op.add_column(
                "attendance_days",
                sa.Column("locked", sa.Boolean(), server_default=sa.false(), nullable=False),
            )
        if dialect == "postgresql":
            op.execute("ALTER TYPE attendance_status ADD VALUE IF NOT EXISTS 'sick'")

    if "course_books" not in tables:
        op.create_table(
            "course_books",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False),
            sa.Column("book_id", sa.Integer(), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("course_id", "book_id", name="uq_course_book"),
        )
        op.create_index("ix_course_books_course_id", "course_books", ["course_id"])
        op.create_index("ix_course_books_book_id", "course_books", ["book_id"])

    if "books" in tables:
        book_cols = {c["name"] for c in insp.get_columns("books")}
        if "course_id" in book_cols:
            if dialect == "postgresql":
                op.execute(
                    sa.text(
                        """
                        INSERT INTO course_books (course_id, book_id, sort_order)
                        SELECT course_id, id, COALESCE(sort_order, 0)
                        FROM books
                        WHERE course_id IS NOT NULL
                        ON CONFLICT (course_id, book_id) DO NOTHING
                        """
                    )
                )
            else:
                op.execute(
                    sa.text(
                        """
                        INSERT OR IGNORE INTO course_books (course_id, book_id, sort_order)
                        SELECT course_id, id, COALESCE(sort_order, 0)
                        FROM books
                        WHERE course_id IS NOT NULL
                        """
                    )
                )
            with op.batch_alter_table("books") as batch:
                batch.drop_column("course_id")
                if "sort_order" in book_cols:
                    batch.drop_column("sort_order")


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "course_books" in tables:
        op.drop_table("course_books")
    if "attendance_days" in tables:
        cols = {c["name"] for c in insp.get_columns("attendance_days")}
        if "locked" in cols:
            op.drop_column("attendance_days", "locked")
    if "users" in tables:
        cols = {c["name"] for c in insp.get_columns("users")}
        if "list_view_preference" in cols:
            op.drop_column("users", "list_view_preference")
