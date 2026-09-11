"""Record and summarize AI spend for teachers."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AiUsageEvent, StudentTeacher, Teacher, User
from app.services.read_pages import PageGuess


def log_event(
    db: Session,
    *,
    user: User,
    student_id: int | None,
    guess: PageGuess,
    key_name: str,
    purpose: str = "read_pages",
) -> AiUsageEvent:
    row = AiUsageEvent(
        user_id=user.id,
        student_id=student_id,
        provider=guess.provider,
        model=guess.model,
        key_name=key_name,
        purpose=purpose,
        prompt_tokens=guess.prompt_tokens,
        completion_tokens=guess.completion_tokens,
        usd=guess.usd,
        status="error" if guess.error else "ok",
        detail=(guess.error or "")[:500],
    )
    db.add(row)
    db.flush()
    return row


def teachers_for_student(db: Session, student_id: int) -> list[int]:
    links = db.scalars(select(StudentTeacher.teacher_id).where(StudentTeacher.student_id == student_id)).all()
    users = db.scalars(select(Teacher.user_id).where(Teacher.id.in_(links))).all() if links else []
    return list(users)


def can_see_usage(db: Session, user: User, student_id: int | None) -> bool:
    if not user.is_teacher:
        return False
    if student_id is None:
        return True
    teacher = db.scalar(select(Teacher).where(Teacher.user_id == user.id))
    if not teacher:
        return False
    link = db.scalar(
        select(StudentTeacher).where(
            StudentTeacher.teacher_id == teacher.id,
            StudentTeacher.student_id == student_id,
        )
    )
    return link is not None


def month_rows(db: Session, when: datetime | None = None) -> list[AiUsageEvent]:
    now = when or datetime.utcnow()
    start = datetime(now.year, now.month, 1)
    return list(
        db.scalars(
            select(AiUsageEvent)
            .where(AiUsageEvent.created_at >= start)
            .order_by(AiUsageEvent.created_at.desc())
        ).all()
    )


def month_total(db: Session, when: datetime | None = None) -> float:
    now = when or datetime.utcnow()
    start = datetime(now.year, now.month, 1)
    value = db.scalar(
        select(func.coalesce(func.sum(AiUsageEvent.usd), 0)).where(AiUsageEvent.created_at >= start)
    )
    return float(value or 0)


def key_month_total(db: Session, user_id: int, key_name: str) -> float:
    now = datetime.utcnow()
    start = datetime(now.year, now.month, 1)
    value = db.scalar(
        select(func.coalesce(func.sum(AiUsageEvent.usd), 0)).where(
            AiUsageEvent.user_id == user_id,
            AiUsageEvent.key_name == key_name,
            AiUsageEvent.created_at >= start,
        )
    )
    return float(value or 0)
