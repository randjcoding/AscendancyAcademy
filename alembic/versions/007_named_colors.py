"""Named colors the family can save and search."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "named_colors" in set(insp.get_table_names()):
        return
    op.create_table(
        "named_colors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("hex", sa.String(length=16), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_index("ix_named_colors_name", "named_colors", ["name"], unique=True)
    op.create_index("ix_named_colors_created_by_user_id", "named_colors", ["created_by_user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "named_colors" in set(insp.get_table_names()):
        op.drop_table("named_colors")
