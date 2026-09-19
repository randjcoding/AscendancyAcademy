"""Learning path progress for capitals."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has_table("activity_path_progress"):
        op.create_table(
            "activity_path_progress",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
            sa.Column("activity_id", sa.String(length=80), nullable=False),
            sa.Column("progress_json", sa.Text(), server_default="{}"),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("student_id", "activity_id", name="uq_activity_path_progress"),
        )
        op.create_index("ix_activity_path_progress_student_id", "activity_path_progress", ["student_id"])
        op.create_index("ix_activity_path_progress_activity_id", "activity_path_progress", ["activity_id"])


def downgrade() -> None:
    if _has_table("activity_path_progress"):
        op.drop_table("activity_path_progress")
