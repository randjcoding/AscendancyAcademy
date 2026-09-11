"""Book kind/ISBN and user density preference."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "books" in set(insp.get_table_names()):
        cols = {c["name"] for c in insp.get_columns("books")}
        if "kind" not in cols:
            op.add_column("books", sa.Column("kind", sa.String(length=20), nullable=False, server_default="other"))
        if "isbn" not in cols:
            op.add_column("books", sa.Column("isbn", sa.String(length=32), nullable=False, server_default=""))
        if "upc" not in cols:
            op.add_column("books", sa.Column("upc", sa.String(length=32), nullable=False, server_default=""))
    if "users" in set(insp.get_table_names()):
        cols = {c["name"] for c in insp.get_columns("users")}
        if "density_preference" not in cols:
            op.add_column(
                "users",
                sa.Column("density_preference", sa.String(length=20), nullable=False, server_default="cozy"),
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "books" in set(insp.get_table_names()):
        cols = {c["name"] for c in insp.get_columns("books")}
        for name in ("upc", "isbn", "kind"):
            if name in cols:
                op.drop_column("books", name)
    if "users" in set(insp.get_table_names()):
        cols = {c["name"] for c in insp.get_columns("users")}
        if "density_preference" in cols:
            op.drop_column("users", "density_preference")
