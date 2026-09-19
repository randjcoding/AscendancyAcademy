"""Activity catalog, attempts, and progress."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.activities.registry import all_activities, get_activity, public_card
from app.activities.schema import ALL_MODES
from app.database import get_db
from app.dependencies import first_student
from app.models import Student, User
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


class PathBody(BaseModel):
    csrf: str = ""
    region: str = ""
    intro_done: bool = False


def _student_id(db, user):
    student = svc.student_for(db, user)
    if student:
        return student.id
    if user.is_teacher:
        other = first_student(db)
        return other.id if other else None
    return None


def _practice_prefs(db, student_id: int | None) -> dict | None:
    if not student_id:
        return None
    student = db.get(Student, student_id)
    if not student:
        return None
    owner = db.get(User, student.user_id) if student.user_id else None
    if not owner:
        return None
    return {
        "user_id": owner.id,
        "name": owner.display_name,
        "spell_help": bool(getattr(owner, "spell_help", True)),
    }


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
    return {"activities": cards, "streak": streak, "practice_prefs": _practice_prefs(db, student_id)}


@router.get("/results")
def results(request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.is_teacher:
        return _err("Teacher required", 403)
    return {"results": svc.teacher_results(db)}


@router.get("/struggle")
def struggle_all(request: Request, activity_id: str = "", db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if user.is_teacher:
        return {"students": svc.teacher_struggle(db, activity_id or None)}
    student = svc.student_for(db, user)
    if not student:
        return {"students": []}
    aid = activity_id or "us-state-capitals"
    return {
        "students": [
            {
                "student_id": student.id,
                "name": student.display_name,
                "activities": [{"activity_id": aid, "hard": [i for i in svc.item_stats(db, student.id, aid) if i["wrong"] > 0]}],
            }
        ]
    }


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
        "struggle": svc.item_stats(db, student_id, activity_id) if student_id else [],
        "path": svc.path_for(db, student_id, activity_id) if student_id else None,
        "practice_prefs": _practice_prefs(db, student_id),
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
    if mode not in ALL_MODES:
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
            bind_student_id=_student_id(db, user),
        )
    except ValueError as exc:
        return _err(str(exc))
    return {"ok": True, **result}


@router.get("/{activity_id}/struggle")
def struggle_one(activity_id: str, request: Request, student_id: int = 0, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not get_activity(activity_id):
        return _err("That activity is gone.", 404)
    sid = student_id if user.is_teacher and student_id else _student_id(db, user)
    items = svc.item_stats(db, sid, activity_id) if sid else []
    return {
        "items": items,
        "need_work": [row for row in items if row["wrong"] > 0],
        "strong": [row for row in items if row["seen"] >= 3 and row["miss_rate"] < 25 and row["wrong"] == 0],
    }


@router.get("/{activity_id}/path")
def get_path(activity_id: str, request: Request, student_id: int = 0, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not get_activity(activity_id):
        return _err("That activity is gone.", 404)
    sid = student_id if user.is_teacher and student_id else _student_id(db, user)
    if not sid:
        return {"path": None}
    return {"path": svc.path_for(db, sid, activity_id)}


@router.post("/{activity_id}/path")
def save_path(activity_id: str, body: PathBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    if not get_activity(activity_id):
        return _err("That activity is gone.", 404)
    student = svc.student_for(db, user)
    if not student:
        sid = _student_id(db, user)
        student = db.get(Student, sid) if sid else None
    if not student:
        return _err("Students save path progress.")
    if not body.intro_done:
        return _err("Mark the intro first.")
    try:
        path = svc.apply_path_intro(db, student.id, activity_id, body.region)
        db.commit()
    except ValueError as exc:
        return _err(str(exc))
    return {"ok": True, "path": path}


@router.get("/{activity_id}/paths")
def list_paths(activity_id: str, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.is_teacher:
        return _err("Teacher required", 403)
    if not get_activity(activity_id):
        return _err("That activity is gone.", 404)
    return {"students": svc.teacher_paths(db, activity_id)}


@router.get("/{activity_id}/history")
def attempt_history(activity_id: str, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    student_id = _student_id(db, user) if user.is_student else None
    return {"history": svc.history(db, student_id=student_id, user_id=user.id, activity_id=activity_id)}
