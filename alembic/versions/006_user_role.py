"""User role for admin and super admin."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "users" not in set(insp.get_table_names()):
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "role" not in cols:
        op.add_column("users", sa.Column("role", sa.String(length=20), server_default="teacher"))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "users" in set(insp.get_table_names()):
        cols = {c["name"] for c in insp.get_columns("users")}
        if "role" in cols:
            op.drop_column("users", "role")
