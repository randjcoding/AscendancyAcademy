"""Idempotent seed: teachers, student, current school year, named API keys."""
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
    TeacherApiKey,
    User,
    UserKind,
)
from app.security import hash_password
from app.services.secrets import encrypt_secret

DEFAULT_CATEGORIES = (
    ("Tests", 40, 0),
    ("Quizzes", 20, 1),
    ("Assignments", 30, 2),
    ("Other", 10, 3),
)

COURSE_COLORS = (
    ("#2D6A4F", "Forest"),
    ("#1D3557", "Navy"),
    ("#9B2226", "Crimson"),
    ("#7B2D8E", "Purple"),
    ("#B45309", "Amber"),
    ("#0F766E", "Teal"),
)
COURSE_COLOR_VALUES = tuple(hex_value for hex_value, _name in COURSE_COLORS)

OLD_TEACHER2_EMAILS = (
    "teacher@ascendancy.local",
    "teacher@example.com",
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
    role: str = "",
    previous_emails: tuple[str, ...] = (),
) -> User:
    email_norm = email.lower().strip()
    user = db.scalar(select(User).where(User.email == email_norm))
    if not user and previous_emails:
        old = [e.lower().strip() for e in previous_emails]
        user = db.scalar(select(User).where(User.email.in_(old)))
        if user:
            user.email = email_norm
            user.first_name = first_name.strip()
            user.last_name = last_name.strip()
            if role:
                user.role = role
            db.add(user)
            db.flush()
            return user
    if user:
        if role:
            user.role = role
            db.add(user)
        return user
    user = User(
        email=email_norm,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        password_hash=hash_password(password),
        kind=kind,
        role=role or ("student" if kind == UserKind.STUDENT else "teacher"),
        is_admin=is_admin,
        status=AccountStatus.ACTIVE,
        must_change_password=True,
        theme_preference="ascendancy",
    )
    db.add(user)
    db.flush()
    return user


def _ensure_named_key(db: Session, user: User, name: str, provider: str, raw: str) -> None:
    secret = (raw or "").strip()
    if not secret:
        return
    existing = db.scalar(
        select(TeacherApiKey).where(
            TeacherApiKey.user_id == user.id,
            TeacherApiKey.provider == provider,
            TeacherApiKey.name == name,
        )
    )
    if existing:
        return
    db.add(
        TeacherApiKey(
            user_id=user.id,
            name=name,
            provider=provider,
            secret_enc=encrypt_secret(secret),
        )
    )


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
            role="super_admin",
        )
        kim = _upsert_user(
            db,
            email=settings.teacher2_email,
            first_name=settings.teacher2_first_name,
            last_name=settings.teacher2_last_name,
            password=settings.teacher2_password,
            kind=UserKind.TEACHER,
            is_admin=True,
            role="teacher",
            previous_emails=OLD_TEACHER2_EMAILS,
        )
        greg = _upsert_user(
            db,
            email=settings.student1_email,
            first_name=settings.student1_first_name,
            last_name=settings.student1_last_name,
            password=settings.student1_password,
            kind=UserKind.STUDENT,
            is_admin=False,
            role="student",
        )

        joe_t = db.scalar(select(Teacher).where(Teacher.user_id == joe.id))
        if not joe_t:
            joe_t = Teacher(user_id=joe.id)
            db.add(joe_t)
            db.flush()
        kim_t = db.scalar(select(Teacher).where(Teacher.user_id == kim.id))
        if not kim_t:
            kim_t = Teacher(user_id=kim.id)
            db.add(kim_t)
            db.flush()
        greg_s = db.scalar(select(Student).where(Student.user_id == greg.id))
        if not greg_s:
            greg_s = Student(user_id=greg.id, preferred_name=settings.student1_first_name)
            db.add(greg_s)
            db.flush()

        for teacher in (joe_t, kim_t):
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

        for teacher_user in (joe, kim):
            _ensure_named_key(db, teacher_user, "OpenAI", "openai", settings.openai_api_key)
            _ensure_named_key(db, teacher_user, "Anthropic", "anthropic", settings.anthropic_api_key)

        db.commit()
    finally:
        if own:
            db.close()
