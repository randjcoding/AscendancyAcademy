"""Parent toggle for the capitals spelling word book."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_col(table: str, name: str) -> bool:
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
    return name in cols


def upgrade() -> None:
    if _has_col("users", "spell_help"):
        return
    op.add_column("users", sa.Column("spell_help", sa.Boolean(), server_default=sa.true()))


def downgrade() -> None:
    if _has_col("users", "spell_help"):
        op.drop_column("users", "spell_help")
