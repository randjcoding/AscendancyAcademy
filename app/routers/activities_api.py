"""Activity catalog, attempts, and progress."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.activities.registry import all_activities, get_activity, public_card
from app.database import get_db
from app.dependencies import first_student
from app.routers.api import _csrf_bad, _err, _must_user
from app.services import activities as svc

router = APIRouter(prefix="/api/activities")


class AttemptBody(BaseModel):
    csrf: str = ""
    mode: str = ""
    score: int = 0
    total: int = 0
    time_taken_seconds: int = 0
    visited: int = 0
    detail: dict = {}


def _student_id(db, user):
    student = svc.student_for(db, user)
    if student:
        return student.id
    if user.is_teacher:
        other = first_student(db)
        return other.id if other else None
    return None


@router.get("")
def list_activities(request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    student_id = _student_id(db, user)
    cards = []
    for activity in all_activities().values():
        prog = svc.progress_row(db, student_id, activity.activity_id) if student_id else None
        cards.append(public_card(activity, prog))
    streak = svc.family_streak(db, student_id) if student_id else 0
    return {"activities": cards, "streak": streak}


@router.get("/results")
def results(request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.is_teacher:
        return _err("Teacher required", 403)
    return {"results": svc.teacher_results(db)}


@router.get("/{activity_id}")
def get_one(activity_id: str, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    activity = get_activity(activity_id)
    if not activity:
        return _err("That activity is gone.", 404)
    student_id = _student_id(db, user)
    places = [p.model_dump() for p in activity.places()]
    return {
        "activity": {
            **public_card(activity, svc.progress_row(db, student_id, activity_id) if student_id else None),
            "content": places,
        },
        "history": svc.history(db, student_id=student_id if user.is_student else None, user_id=user.id, activity_id=activity_id)
        if user.is_student or user.is_teacher
        else [],
    }


@router.post("/{activity_id}/attempt")
def save_attempt(activity_id: str, body: AttemptBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    if not get_activity(activity_id):
        return _err("That activity is gone.", 404)
    mode = (body.mode or "").strip()
    if mode not in {"study", "find_on_map", "name_the_capital", "flashcards"}:
        return _err("Pick a mode first.")
    detail = dict(body.detail or {})
    if body.visited:
        detail["visited"] = body.visited
    try:
        result = svc.record_attempt(
            db,
            user=user,
            activity_id=activity_id,
            mode=mode,
            score=body.score,
            total=body.total,
            time_taken_seconds=body.time_taken_seconds,
            detail=detail,
        )
    except ValueError as exc:
        return _err(str(exc))
    return {"ok": True, **result}


@router.get("/{activity_id}/history")
def attempt_history(activity_id: str, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    student_id = _student_id(db, user) if user.is_student else None
    return {"history": svc.history(db, student_id=student_id, user_id=user.id, activity_id=activity_id)}
