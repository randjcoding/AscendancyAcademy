"""Idempotent seed: teachers, student, current school year."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import (
    AccountStatus,
    SchoolYear,
    Student,
    StudentTeacher,
    Teacher,
    User,
    UserKind,
)
from app.security import hash_password

DEFAULT_CATEGORIES = (
    ("Tests", 40, 0),
    ("Quizzes", 20, 1),
    ("Assignments", 30, 2),
    ("Other", 10, 3),
)

COURSE_COLORS = (
    "#2D6A4F",
    "#1D3557",
    "#9B2226",
    "#7B2D8E",
    "#B45309",
    "#0F766E",
)


def _upsert_user(
    db: Session,
    *,
    email: str,
    first_name: str,
    last_name: str,
    password: str,
    kind: UserKind,
    is_admin: bool,
) -> User:
    email_norm = email.lower().strip()
    user = db.scalar(select(User).where(User.email == email_norm))
    if user:
        return user
    user = User(
        email=email_norm,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        password_hash=hash_password(password),
        kind=kind,
        is_admin=is_admin,
        status=AccountStatus.ACTIVE,
        must_change_password=True,
        theme_preference="ascendancy",
    )
    db.add(user)
    db.flush()
    return user


def seed(db: Session | None = None) -> None:
    own = db is None
    if own:
        db = SessionLocal()
    try:
        joe = _upsert_user(
            db,
            email=settings.teacher1_email,
            first_name=settings.teacher1_first_name,
            last_name=settings.teacher1_last_name,
            password=settings.teacher1_password,
            kind=UserKind.TEACHER,
            is_admin=True,
        )
        wife = _upsert_user(
            db,
            email=settings.teacher2_email,
            first_name=settings.teacher2_first_name,
            last_name=settings.teacher2_last_name,
            password=settings.teacher2_password,
            kind=UserKind.TEACHER,
            is_admin=True,
        )
        greg = _upsert_user(
            db,
            email=settings.student1_email,
            first_name=settings.student1_first_name,
            last_name=settings.student1_last_name,
            password=settings.student1_password,
            kind=UserKind.STUDENT,
            is_admin=False,
        )

        joe_t = db.scalar(select(Teacher).where(Teacher.user_id == joe.id))
        if not joe_t:
            joe_t = Teacher(user_id=joe.id)
            db.add(joe_t)
            db.flush()
        wife_t = db.scalar(select(Teacher).where(Teacher.user_id == wife.id))
        if not wife_t:
            wife_t = Teacher(user_id=wife.id)
            db.add(wife_t)
            db.flush()
        greg_s = db.scalar(select(Student).where(Student.user_id == greg.id))
        if not greg_s:
            greg_s = Student(user_id=greg.id, preferred_name=settings.student1_first_name)
            db.add(greg_s)
            db.flush()

        for teacher in (joe_t, wife_t):
            link = db.scalar(
                select(StudentTeacher).where(
                    StudentTeacher.student_id == greg_s.id,
                    StudentTeacher.teacher_id == teacher.id,
                )
            )
            if not link:
                db.add(StudentTeacher(student_id=greg_s.id, teacher_id=teacher.id))

        year = db.scalar(select(SchoolYear).where(SchoolYear.label == "2026-2027"))
        if not year:
            year = SchoolYear(
                label="2026-2027",
                start_date=date(2026, 8, 1),
                end_date=date(2027, 5, 31),
                instructional_day_target=180,
                is_current=True,
            )
            db.add(year)
        else:
            year.is_current = True

        for user in db.scalars(select(User)).all():
            if user.theme_preference == "academy":
                user.theme_preference = "ascendancy"

        db.commit()
    finally:
        if own:
            db.close()
