"""Test Maker: assessments, questions, attempts, and answers."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "assessments" not in tables:
        op.create_table(
            "assessments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String(length=255), server_default="Untitled test"),
            sa.Column("instructions", sa.Text(), server_default=""),
            sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id", ondelete="SET NULL"), nullable=True),
            sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_text", sa.Text(), server_default=""),
            sa.Column("model_provider", sa.String(length=32), server_default=""),
            sa.Column("model_name", sa.String(length=80), server_default=""),
            sa.Column("status", sa.String(length=16), server_default="draft"),
            sa.Column("allow_retries", sa.Boolean(), server_default=sa.false()),
            sa.Column("retry_credit", sa.String(length=8), server_default="full"),
            sa.Column("shuffle", sa.Boolean(), server_default=sa.false()),
            sa.Column("points_possible", sa.Float(), server_default="0"),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
            sa.Column("deleted_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_assessments_course_id", "assessments", ["course_id"])
        op.create_index("ix_assessments_status", "assessments", ["status"])
        op.create_index("ix_assessments_created_by_user_id", "assessments", ["created_by_user_id"])
        op.create_index("ix_assessments_deleted_at", "assessments", ["deleted_at"])

    if "assessment_questions" not in tables:
        op.create_table(
            "assessment_questions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("assessment_id", sa.Integer(), sa.ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sort_order", sa.Integer(), server_default="0"),
            sa.Column("type", sa.String(length=8), server_default="mc"),
            sa.Column("prompt", sa.Text(), server_default=""),
            sa.Column("points", sa.Float(), server_default="1"),
            sa.Column("data_json", sa.Text(), server_default=""),
            sa.Column("explanation", sa.Text(), server_default=""),
        )
        op.create_index("ix_assessment_questions_assessment_id", "assessment_questions", ["assessment_id"])

    if "assessment_attempts" not in tables:
        op.create_table(
            "assessment_attempts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("assessment_id", sa.Integer(), sa.ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id", ondelete="CASCADE"), nullable=False),
            sa.Column("enrollment_id", sa.Integer(), sa.ForeignKey("enrollments.id", ondelete="SET NULL"), nullable=True),
            sa.Column("attempt_no", sa.Integer(), server_default="1"),
            sa.Column("status", sa.String(length=16), server_default="in_progress"),
            sa.Column("score_points", sa.Float(), server_default="0"),
            sa.Column("score_possible", sa.Float(), server_default="0"),
            sa.Column("percent", sa.Float(), nullable=True),
            sa.Column("grade_id", sa.Integer(), sa.ForeignKey("grades.id", ondelete="SET NULL"), nullable=True),
            sa.Column("started_at", sa.DateTime()),
            sa.Column("submitted_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_assessment_attempts_assessment_id", "assessment_attempts", ["assessment_id"])
        op.create_index("ix_assessment_attempts_student_id", "assessment_attempts", ["student_id"])
        op.create_index("ix_assessment_attempts_status", "assessment_attempts", ["status"])

    if "assessment_answers" not in tables:
        op.create_table(
            "assessment_answers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("assessment_attempts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("question_id", sa.Integer(), sa.ForeignKey("assessment_questions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("response_json", sa.Text(), server_default=""),
            sa.Column("is_correct", sa.Boolean(), server_default=sa.false()),
            sa.Column("points_earned", sa.Float(), server_default="0"),
            sa.Column("retried", sa.Boolean(), server_default=sa.false()),
            sa.Column("first_correct", sa.Boolean(), server_default=sa.false()),
        )
        op.create_index("ix_assessment_answers_attempt_id", "assessment_answers", ["attempt_id"])
        op.create_index("ix_assessment_answers_question_id", "assessment_answers", ["question_id"])


def downgrade() -> None:
    op.drop_table("assessment_answers")
    op.drop_table("assessment_attempts")
    op.drop_table("assessment_questions")
    op.drop_table("assessments")
