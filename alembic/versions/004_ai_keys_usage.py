"""Teacher API keys and AI usage events."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "teacher_api_keys" not in tables:
        op.create_table(
            "teacher_api_keys",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(length=80), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("secret_enc", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    if "ai_usage_events" not in tables:
        op.create_table(
            "ai_usage_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="SET NULL"), nullable=True),
            sa.Column("provider", sa.String(length=32), nullable=False),
            sa.Column("model", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("key_name", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("purpose", sa.String(length=40), nullable=False, server_default="read_pages"),
            sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("usd", sa.Float(), nullable=False, server_default="0"),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="ok"),
            sa.Column("detail", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "ai_usage_events" in tables:
        op.drop_table("ai_usage_events")
    if "teacher_api_keys" in tables:
        op.drop_table("teacher_api_keys")
