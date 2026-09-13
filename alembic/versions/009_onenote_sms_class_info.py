"""OneNote boxes, SMS reminders, class info, and phones."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add(table: str, name: str, col: sa.Column) -> None:
    insp = sa.inspect(op.get_bind())
    if table not in set(insp.get_table_names()):
        return
    cols = {c["name"] for c in insp.get_columns(table)}
    if name not in cols:
        op.add_column(table, col)


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "users" in tables:
        _add("users", "phone", sa.Column("phone", sa.String(length=32), nullable=True))

    if "notebooks" in tables:
        _add("notebooks", "color", sa.Column("color", sa.String(length=16), server_default="#d4b44a"))
        _add("notebooks", "archived", sa.Column("archived", sa.Boolean(), server_default=sa.false()))

    if "note_sections" in tables:
        _add("note_sections", "color", sa.Column("color", sa.String(length=16), server_default="#2d6a4f"))

    if "courses" in tables:
        for name, col in (
            ("description", sa.Column("description", sa.Text(), server_default="")),
            ("schedule", sa.Column("schedule", sa.String(length=255), server_default="")),
            ("location", sa.Column("location", sa.String(length=160), server_default="")),
            ("grade_level", sa.Column("grade_level", sa.String(length=80), server_default="")),
            ("credit_hours", sa.Column("credit_hours", sa.String(length=40), server_default="")),
            ("goals", sa.Column("goals", sa.Text(), server_default="")),
            ("materials", sa.Column("materials", sa.Text(), server_default="")),
            ("teacher_notes", sa.Column("teacher_notes", sa.Text(), server_default="")),
            ("student_brief", sa.Column("student_brief", sa.Text(), server_default="")),
        ):
            _add("courses", name, col)

    if "reminder_jobs" in tables:
        _add("reminder_jobs", "channel", sa.Column("channel", sa.String(length=16), server_default="email"))
        _add("reminder_jobs", "sms_to", sa.Column("sms_to", sa.String(length=32), nullable=True))
        _add("reminder_jobs", "sms_delivered_for", sa.Column("sms_delivered_for", sa.DateTime(), nullable=True))

    if "note_boxes" not in tables:
        op.create_table(
            "note_boxes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("page_id", sa.Integer(), sa.ForeignKey("note_pages.id", ondelete="CASCADE"), nullable=False),
            sa.Column("revision", sa.Integer(), server_default="0"),
            sa.Column("x", sa.Integer(), server_default="40"),
            sa.Column("y", sa.Integer(), server_default="24"),
            sa.Column("w", sa.Integer(), server_default="720"),
            sa.Column("h", sa.Integer(), server_default="160"),
            sa.Column("z", sa.Integer(), server_default="1"),
            sa.Column("bg", sa.Text(), server_default=""),
            sa.Column("body_html", sa.Text(), server_default=""),
            sa.Column("body_json", sa.Text(), server_default=""),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
        )
        op.create_index("ix_note_boxes_page_id", "note_boxes", ["page_id"])


def downgrade() -> None:
    op.drop_table("note_boxes")
