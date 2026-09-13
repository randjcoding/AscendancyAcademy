"""Notes, task scope, reminders, and page-task links."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "tasks" in tables:
        cols = {c["name"] for c in insp.get_columns("tasks")}
        if "scope" not in cols:
            op.add_column("tasks", sa.Column("scope", sa.String(length=16), server_default="school"))
            op.create_index("ix_tasks_scope", "tasks", ["scope"])
        if "owner_user_id" not in cols:
            op.add_column("tasks", sa.Column("owner_user_id", sa.Integer(), nullable=True))
            op.create_index("ix_tasks_owner_user_id", "tasks", ["owner_user_id"])
            op.execute("UPDATE tasks SET owner_user_id = created_by_user_id WHERE owner_user_id IS NULL")
        if "course_id" not in cols:
            op.add_column("tasks", sa.Column("course_id", sa.Integer(), nullable=True))
            op.create_index("ix_tasks_course_id", "tasks", ["course_id"])
        if "priority" not in cols:
            op.add_column("tasks", sa.Column("priority", sa.Integer(), server_default="0"))
        if "inbox" not in cols:
            op.add_column("tasks", sa.Column("inbox", sa.Boolean(), server_default=sa.false()))
            op.create_index("ix_tasks_inbox", "tasks", ["inbox"])

    if "notebooks" not in tables:
        op.create_table(
            "notebooks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("scope", sa.String(length=16), nullable=False, server_default="personal"),
            sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="CASCADE"), nullable=True),
            sa.Column("sort_order", sa.Integer(), server_default="0"),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime()),
        )
        op.create_index("ix_notebooks_scope", "notebooks", ["scope"])
        op.create_index("ix_notebooks_owner_user_id", "notebooks", ["owner_user_id"])
        op.create_index("ix_notebooks_course_id", "notebooks", ["course_id"])
        op.create_index("ix_notebooks_deleted_at", "notebooks", ["deleted_at"])

    if "note_sections" not in tables:
        op.create_table(
            "note_sections",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("notebook_id", sa.Integer(), sa.ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(length=160), server_default="Pages"),
            sa.Column("sort_order", sa.Integer(), server_default="0"),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime()),
        )
        op.create_index("ix_note_sections_notebook_id", "note_sections", ["notebook_id"])
        op.create_index("ix_note_sections_deleted_at", "note_sections", ["deleted_at"])

    if "note_pages" not in tables:
        op.create_table(
            "note_pages",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("notebook_id", sa.Integer(), sa.ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("section_id", sa.Integer(), sa.ForeignKey("note_sections.id", ondelete="SET NULL"), nullable=True),
            sa.Column("parent_id", sa.Integer(), sa.ForeignKey("note_pages.id", ondelete="CASCADE"), nullable=True),
            sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("scope", sa.String(length=16), nullable=False, server_default="personal"),
            sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="SET NULL"), nullable=True),
            sa.Column("title", sa.String(length=255), server_default="Untitled"),
            sa.Column("kind", sa.String(length=16), server_default="note"),
            sa.Column("body_html", sa.Text(), server_default=""),
            sa.Column("body_json", sa.Text(), server_default=""),
            sa.Column("body_plain", sa.Text(), server_default=""),
            sa.Column("revision", sa.Integer(), server_default="0"),
            sa.Column("sort_order", sa.Integer(), server_default="0"),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
        )
        op.create_index("ix_note_pages_notebook_id", "note_pages", ["notebook_id"])
        op.create_index("ix_note_pages_section_id", "note_pages", ["section_id"])
        op.create_index("ix_note_pages_parent_id", "note_pages", ["parent_id"])
        op.create_index("ix_note_pages_owner_user_id", "note_pages", ["owner_user_id"])
        op.create_index("ix_note_pages_scope", "note_pages", ["scope"])
        op.create_index("ix_note_pages_course_id", "note_pages", ["course_id"])
        op.create_index("ix_note_pages_deleted_at", "note_pages", ["deleted_at"])

    if "note_history" not in tables:
        op.create_table(
            "note_history",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("page_id", sa.Integer(), sa.ForeignKey("note_pages.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(length=255), server_default=""),
            sa.Column("body_html", sa.Text(), server_default=""),
            sa.Column("body_json", sa.Text(), server_default=""),
            sa.Column("created_at", sa.DateTime()),
        )
        op.create_index("ix_note_history_page_id", "note_history", ["page_id"])
        op.create_index("ix_note_history_created_at", "note_history", ["created_at"])

    if "page_tasks" not in tables:
        op.create_table(
            "page_tasks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("page_id", sa.Integer(), sa.ForeignKey("note_pages.id", ondelete="CASCADE"), nullable=False),
            sa.Column("task_id", sa.Integer(), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("created_at", sa.DateTime()),
            sa.UniqueConstraint("page_id", "task_id", name="uq_page_task"),
        )
        op.create_index("ix_page_tasks_page_id", "page_tasks", ["page_id"])
        op.create_index("ix_page_tasks_task_id", "page_tasks", ["task_id"])

    if "reminder_jobs" not in tables:
        op.create_table(
            "reminder_jobs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(length=160), nullable=True),
            sa.Column("send_at", sa.DateTime(), nullable=False),
            sa.Column("subject", sa.String(length=255), server_default=""),
            sa.Column("body", sa.Text(), server_default=""),
            sa.Column("recipient", sa.String(length=255), server_default=""),
            sa.Column("audience", sa.String(length=16), server_default="personal"),
            sa.Column("recurrence", sa.String(length=32), server_default=""),
            sa.Column("recurrence_json", sa.Text(), server_default=""),
            sa.Column("repeat_until", sa.Date(), nullable=True),
            sa.Column("series_start", sa.DateTime(), nullable=True),
            sa.Column("status", sa.String(length=16), server_default="pending"),
            sa.Column("last_sent_at", sa.DateTime(), nullable=True),
            sa.Column("email_delivered_for", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime()),
        )
        op.create_index("ix_reminder_jobs_user_id", "reminder_jobs", ["user_id"])
        op.create_index("ix_reminder_jobs_send_at", "reminder_jobs", ["send_at"])
        op.create_index("ix_reminder_jobs_status", "reminder_jobs", ["status"])

    if "reminder_items" not in tables:
        op.create_table(
            "reminder_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("reminder_id", sa.Integer(), sa.ForeignKey("reminder_jobs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("item_type", sa.String(length=16), nullable=False),
            sa.Column("item_id", sa.Integer(), nullable=True),
            sa.Column("text", sa.String(length=500), server_default=""),
            sa.Column("sort_order", sa.Integer(), server_default="0"),
            sa.Column("created_at", sa.DateTime()),
        )
        op.create_index("ix_reminder_items_reminder_id", "reminder_items", ["reminder_id"])


def downgrade() -> None:
    op.drop_table("reminder_items")
    op.drop_table("reminder_jobs")
    op.drop_table("page_tasks")
    op.drop_table("note_history")
    op.drop_table("note_pages")
    op.drop_table("note_sections")
    op.drop_table("notebooks")
