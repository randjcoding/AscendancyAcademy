"""Activities engine, nicknames, sound toggle, and AI grants."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _has_col(table: str, name: str) -> bool:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
    return name in cols


def upgrade() -> None:
    if _has_table("users"):
        if not _has_col("users", "nickname"):
            op.add_column("users", sa.Column("nickname", sa.String(length=80), server_default=""))
        if not _has_col("users", "sound_enabled"):
            op.add_column("users", sa.Column("sound_enabled", sa.Boolean(), server_default=sa.true()))

    if not _has_table("activity_attempts"):
        op.create_table(
            "activity_attempts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="SET NULL"), nullable=True),
            sa.Column("activity_id", sa.String(length=80), nullable=False),
            sa.Column("mode", sa.String(length=32), server_default=""),
            sa.Column("score", sa.Integer(), server_default="0"),
            sa.Column("total", sa.Integer(), server_default="0"),
            sa.Column("accuracy", sa.Float(), server_default="0"),
            sa.Column("time_taken_seconds", sa.Integer(), server_default="0"),
            sa.Column("stars_earned", sa.Integer(), server_default="0"),
            sa.Column("detail_json", sa.Text(), server_default=""),
            sa.Column("created_at", sa.DateTime()),
        )
        op.create_index("ix_activity_attempts_user_id", "activity_attempts", ["user_id"])
        op.create_index("ix_activity_attempts_student_id", "activity_attempts", ["student_id"])
        op.create_index("ix_activity_attempts_activity_id", "activity_attempts", ["activity_id"])

    if not _has_table("activity_progress"):
        op.create_table(
            "activity_progress",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
            sa.Column("activity_id", sa.String(length=80), nullable=False),
            sa.Column("best_accuracy", sa.Float(), server_default="0"),
            sa.Column("best_stars", sa.Integer(), server_default="0"),
            sa.Column("plays", sa.Integer(), server_default="0"),
            sa.Column("streak", sa.Integer(), server_default="0"),
            sa.Column("last_played_on", sa.Date(), nullable=True),
            sa.Column("updated_at", sa.DateTime()),
            sa.UniqueConstraint("student_id", "activity_id", name="uq_activity_progress"),
        )
        op.create_index("ix_activity_progress_student_id", "activity_progress", ["student_id"])
        op.create_index("ix_activity_progress_activity_id", "activity_progress", ["activity_id"])

    if not _has_table("user_ai_grants"):
        op.create_table(
            "user_ai_grants",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("purpose", sa.String(length=40), nullable=False),
            sa.Column("created_at", sa.DateTime()),
            sa.UniqueConstraint("user_id", "purpose", name="uq_user_ai_grant"),
        )
        op.create_index("ix_user_ai_grants_user_id", "user_ai_grants", ["user_id"])


def downgrade() -> None:
    op.drop_table("user_ai_grants")
    op.drop_table("activity_progress")
    op.drop_table("activity_attempts")
    if _has_table("users"):
        if _has_col("users", "sound_enabled"):
            op.drop_column("users", "sound_enabled")
        if _has_col("users", "nickname"):
            op.drop_column("users", "nickname")
