"""All-time notebooks and per-item activity struggle stats."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_col(table: str, name: str) -> bool:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
    return name in cols


def upgrade() -> None:
    if _has_table("notebooks"):
        if not _has_col("notebooks", "lifetime"):
            op.add_column("notebooks", sa.Column("lifetime", sa.Boolean(), server_default=sa.false()))
        if not _has_col("notebooks", "school_year_id"):
            op.add_column(
                "notebooks",
                sa.Column("school_year_id", sa.Integer(), sa.ForeignKey("school_years.id", ondelete="SET NULL"), nullable=True),
            )
        op.execute("UPDATE notebooks SET lifetime = TRUE WHERE course_id IS NULL AND deleted_at IS NULL")

    if not _has_table("activity_item_stats"):
        op.create_table(
            "activity_item_stats",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
            sa.Column("activity_id", sa.String(length=80), nullable=False),
            sa.Column("item_id", sa.String(length=16), nullable=False),
            sa.Column("seen", sa.Integer(), server_default="0"),
            sa.Column("correct", sa.Integer(), server_default="0"),
            sa.Column("wrong", sa.Integer(), server_default="0"),
            sa.Column("last_wrong_at", sa.DateTime(), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("student_id", "activity_id", "item_id", name="uq_activity_item_stat"),
        )
        op.create_index("ix_activity_item_stats_student_id", "activity_item_stats", ["student_id"])
        op.create_index("ix_activity_item_stats_activity_id", "activity_item_stats", ["activity_id"])


def downgrade() -> None:
    if _has_table("activity_item_stats"):
        op.drop_table("activity_item_stats")
    if _has_table("notebooks"):
        if _has_col("notebooks", "school_year_id"):
            op.drop_column("notebooks", "school_year_id")
        if _has_col("notebooks", "lifetime"):
            op.drop_column("notebooks", "lifetime")
