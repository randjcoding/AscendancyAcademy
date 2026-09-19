"""Joe-only super admin: people, AI grants, activity snapshot."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.activities.schema import AI_PURPOSES
from app.database import get_db
from app.models import Student, StudentTeacher, Teacher, User, UserAiGrant, UserKind
from app.routers.api import _csrf_bad, _err, _must_user
from app.security import hash_password
from app.services import activities as act_svc

router = APIRouter(prefix="/api/admin")


class GrantBody(BaseModel):
    csrf: str = ""
    user_id: int
    purpose: str
    allowed: bool = True


class AddPersonBody(BaseModel):
    csrf: str = ""
    email: str
    first_name: str
    last_name: str = ""
    nickname: str = ""
    kind: str = "student"
    password: str


def _super(request: Request, db: Session):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if not user.is_super_admin:
        return _err("Only Joe can open this.", 403)
    return user


def _person_json(db: Session, person: User) -> dict:
    return {
        "id": person.id,
        "name": person.display_name,
        "full_name": person.full_name,
        "nickname": person.nickname or "",
        "email": person.email,
        "phone": person.phone or "",
        "role": person.role,
        "kind": person.kind.value,
        "ai_grants": act_svc.grant_list(db, person.id),
        "can_use_ai": act_svc.can_use_ai(db, person),
    }


@router.get("/people")
def admin_people(request: Request, db: Session = Depends(get_db)):
    user = _super(request, db)
    if isinstance(user, JSONResponse):
        return user
    people = db.scalars(select(User).order_by(User.first_name)).all()
    return {"people": [_person_json(db, p) for p in people], "purposes": list(AI_PURPOSES)}


@router.post("/people")
def add_person(body: AddPersonBody, request: Request, db: Session = Depends(get_db)):
    user = _super(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    email = body.email.lower().strip()
    if not email or "@" not in email:
        return _err("Need a real email.")
    if len(body.password) < 10:
        return _err("Password must be at least 10 characters.")
    if db.scalar(select(User).where(User.email == email)):
        return _err("That email is already in use.")
    kind = UserKind.STUDENT if body.kind == "student" else UserKind.TEACHER
    person = User(
        email=email,
        first_name=body.first_name.strip()[:80],
        last_name=body.last_name.strip()[:80],
        nickname=body.nickname.strip()[:80],
        password_hash=hash_password(body.password),
        kind=kind,
        role="student" if kind == UserKind.STUDENT else "teacher",
        is_admin=kind == UserKind.TEACHER,
        must_change_password=True,
    )
    db.add(person)
    db.flush()
    if kind == UserKind.TEACHER:
        db.add(Teacher(user_id=person.id))
    else:
        student = Student(user_id=person.id, preferred_name=person.nickname or person.first_name)
        db.add(student)
        db.flush()
        teachers = db.scalars(select(Teacher)).all()
        for teacher in teachers:
            db.add(StudentTeacher(student_id=student.id, teacher_id=teacher.id))
    db.commit()
    return {"ok": True, "person": _person_json(db, person)}


@router.post("/ai-grant")
def set_grant(body: GrantBody, request: Request, db: Session = Depends(get_db)):
    user = _super(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    if body.purpose not in AI_PURPOSES:
        return _err("Unknown AI use.")
    target = db.get(User, body.user_id)
    if not target:
        return _err("Person not found.")
    existing = db.scalar(
        select(UserAiGrant).where(UserAiGrant.user_id == target.id, UserAiGrant.purpose == body.purpose)
    )
    if body.allowed and not existing:
        db.add(UserAiGrant(user_id=target.id, purpose=body.purpose))
    if not body.allowed and existing:
        db.delete(existing)
    db.commit()
    return {"ok": True, "grants": act_svc.grant_list(db, target.id)}


@router.get("/activities")
def admin_activities(request: Request, db: Session = Depends(get_db)):
    user = _super(request, db)
    if isinstance(user, JSONResponse):
        return user
    return {"results": act_svc.teacher_results(db)}
