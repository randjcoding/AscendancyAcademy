"""Record activity attempts, stars, and play streaks."""
from __future__ import annotations

import json
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.activities.registry import get_activity
from app.activities.schema import stars_for
from app.models import ActivityAttempt, ActivityProgress, Student, User, UserAiGrant
from app.services.clock import house_today


def can_use_ai(db: Session, user: User, purpose: str | None = None) -> bool:
    if user.is_teacher:
        return True
    grants = list(db.scalars(select(UserAiGrant.purpose).where(UserAiGrant.user_id == user.id)).all())
    if purpose:
        return purpose in grants
    return bool(grants)


def grant_list(db: Session, user_id: int) -> list[str]:
    return list(db.scalars(select(UserAiGrant.purpose).where(UserAiGrant.user_id == user_id)).all())


def student_for(db: Session, user: User) -> Student | None:
    if user.is_student:
        return db.scalar(select(Student).where(Student.user_id == user.id))
    return None


def progress_row(db: Session, student_id: int, activity_id: str) -> dict:
    row = db.scalar(
        select(ActivityProgress).where(
            ActivityProgress.student_id == student_id,
            ActivityProgress.activity_id == activity_id,
        )
    )
    if not row:
        return {
            "best_accuracy": 0,
            "best_stars": 0,
            "plays": 0,
            "streak": 0,
            "last_played_on": "",
        }
    return {
        "best_accuracy": row.best_accuracy,
        "best_stars": row.best_stars,
        "plays": row.plays,
        "streak": row.streak,
        "last_played_on": row.last_played_on.isoformat() if row.last_played_on else "",
    }


def family_streak(db: Session, student_id: int) -> int:
    """Longest current daily streak across all activities."""
    rows = db.scalars(select(ActivityProgress).where(ActivityProgress.student_id == student_id)).all()
    return max((r.streak for r in rows), default=0)


def record_attempt(
    db: Session,
    *,
    user: User,
    activity_id: str,
    mode: str,
    score: int,
    total: int,
    time_taken_seconds: int,
    detail: dict | None = None,
) -> dict:
    activity = get_activity(activity_id)
    if not activity:
        raise ValueError("That activity is gone.")
    score = max(0, int(score))
    total = max(0, int(total))
    accuracy = round((score / total) * 100.0, 2) if total else 0.0
    finished = total > 0 or mode == "study"
    if mode == "study":
        visited = int((detail or {}).get("visited") or score)
        finished = visited >= 10
        accuracy = 0.0
        score = visited
        total = len(activity.content) or 50
    stars = stars_for(activity.passing_criteria, finished=finished, accuracy=accuracy)
    student = student_for(db, user)
    attempt = ActivityAttempt(
        user_id=user.id,
        student_id=student.id if student else None,
        activity_id=activity_id,
        mode=mode,
        score=score,
        total=total,
        accuracy=accuracy,
        time_taken_seconds=max(0, int(time_taken_seconds)),
        stars_earned=stars,
        detail_json=json.dumps(detail or {}),
    )
    db.add(attempt)
    progress = None
    if student:
        progress = _bump_progress(db, student.id, activity_id, accuracy, stars, finished)
    db.commit()
    db.refresh(attempt)
    return {
        "attempt_id": attempt.id,
        "stars_earned": stars,
        "accuracy": accuracy,
        "score": score,
        "total": total,
        "progress": progress_row(db, student.id, activity_id) if student else None,
        "streak": progress.streak if progress else 0,
    }


def _bump_progress(
    db: Session,
    student_id: int,
    activity_id: str,
    accuracy: float,
    stars: int,
    finished: bool,
) -> ActivityProgress:
    row = db.scalar(
        select(ActivityProgress).where(
            ActivityProgress.student_id == student_id,
            ActivityProgress.activity_id == activity_id,
        )
    )
    today = house_today()
    if not row:
        row = ActivityProgress(
            student_id=student_id,
            activity_id=activity_id,
            best_accuracy=accuracy if finished else 0,
            best_stars=stars,
            plays=1 if finished else 0,
            streak=1 if finished else 0,
            last_played_on=today if finished else None,
        )
        db.add(row)
        db.flush()
        return row
    if finished:
        row.plays = (row.plays or 0) + 1
        row.best_accuracy = max(row.best_accuracy or 0, accuracy)
        row.best_stars = max(row.best_stars or 0, stars)
        last = row.last_played_on
        if last == today:
            pass
        elif last == today - timedelta(days=1):
            row.streak = (row.streak or 0) + 1
        else:
            row.streak = 1
        row.last_played_on = today
    db.flush()
    return row


def history(db: Session, *, student_id: int | None, user_id: int, activity_id: str, limit: int = 20) -> list[dict]:
    q = select(ActivityAttempt).where(ActivityAttempt.activity_id == activity_id)
    if student_id:
        q = q.where(ActivityAttempt.student_id == student_id)
    else:
        q = q.where(ActivityAttempt.user_id == user_id)
    rows = db.scalars(q.order_by(ActivityAttempt.created_at.desc()).limit(limit)).all()
    return [
        {
            "id": r.id,
            "mode": r.mode,
            "score": r.score,
            "total": r.total,
            "accuracy": r.accuracy,
            "stars": r.stars_earned,
            "seconds": r.time_taken_seconds,
            "when": r.created_at.isoformat() if r.created_at else "",
        }
        for r in rows
    ]


def teacher_results(db: Session) -> list[dict]:
    students = db.scalars(select(Student).order_by(Student.id)).all()
    out = []
    for student in students:
        name = student.display_name
        rows = db.scalars(select(ActivityProgress).where(ActivityProgress.student_id == student.id)).all()
        out.append(
            {
                "student_id": student.id,
                "name": name,
                "streak": max((r.streak for r in rows), default=0),
                "activities": [
                    {
                        "activity_id": r.activity_id,
                        "best_stars": r.best_stars,
                        "best_accuracy": r.best_accuracy,
                        "plays": r.plays,
                    }
                    for r in rows
                ],
            }
        )
    return out
