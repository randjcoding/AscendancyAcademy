"""Shared FastAPI dependencies."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import BASE_DIR, settings
from app.database import get_db
from app.models import Student, Teacher, User, UserKind
from app.security import csrf_token_for, get_user_by_session
from app.services.attendance import current_year

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))

THEMES = ["academy", "light", "dark", "contrast", "forest", "parchment"]
DENSITIES = ["comfortable", "cozy", "compact"]
THEME_LABELS = {
    "academy": "Academy",
    "light": "Light",
    "dark": "Dark",
    "contrast": "High contrast",
    "forest": "Forest",
    "parchment": "Parchment",
}
DENSITY_LABELS = {
    "comfortable": "Roomy",
    "cozy": "Cozy",
    "compact": "Compact",
}


def session_token(request: Request) -> str | None:
    return request.cookies.get(settings.session_cookie_name)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    return get_user_by_session(db, session_token(request))


def require_login(user: User | None = Depends(get_current_user)) -> User:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login required")
    return user


def require_password_changed(user: User = Depends(require_login)) -> User:
    if user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password change required",
        )
    return user


def require_teacher(user: User = Depends(require_password_changed)) -> User:
    if user.kind != UserKind.TEACHER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Teacher required")
    return user


def require_student(user: User = Depends(require_password_changed)) -> User:
    if user.kind != UserKind.STUDENT:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student required")
    return user


def teacher_profile(db: Session, user: User) -> Teacher:
    profile = db.scalar(select(Teacher).where(Teacher.user_id == user.id))
    if not profile:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Teacher profile missing")
    return profile


def student_profile(db: Session, user: User) -> Student:
    profile = db.scalar(select(Student).where(Student.user_id == user.id))
    if not profile:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Student profile missing")
    return profile


def first_student(db: Session) -> Student | None:
    return db.scalar(select(Student).order_by(Student.id.asc()))


def theme_for(request: Request, user: User | None) -> str:
    cookie = (request.cookies.get("aa_theme") or "").strip()
    if user and user.theme_preference in THEMES:
        return user.theme_preference
    if cookie in THEMES:
        return cookie
    return "academy"


def density_for(request: Request, user: User | None) -> str:
    cookie = (request.cookies.get("aa_density") or "").strip()
    if user and getattr(user, "density_preference", None) in DENSITIES:
        return user.density_preference
    if cookie in DENSITIES:
        return cookie
    return "cozy"


def base_context(request: Request, user: User | None, **extra) -> dict:
    from app.models import BOOK_KIND_LABELS, BookKind
    from app.services.turnstile import turnstile_required

    token = session_token(request)
    db = extra.pop("_db", None)
    year = extra.pop("school_year", None)
    if db is not None and year is None:
        year = current_year(db)
    return {
        "request": request,
        "settings": settings,
        "current_user": user,
        "site_name": settings.site_name,
        "turnstile_enabled": turnstile_required(request),
        "turnstile_site_key": settings.turnstile_site_key,
        "csrf_token": csrf_token_for(token) if token else "",
        "theme": theme_for(request, user),
        "density": density_for(request, user),
        "themes": THEMES,
        "theme_labels": THEME_LABELS,
        "densities": DENSITIES,
        "density_labels": DENSITY_LABELS,
        "book_kinds": [(k.value, BOOK_KIND_LABELS[k]) for k in BookKind],
        "school_year": year,
        **extra,
    }


def render(request: Request, name: str, user: User | None, **extra):
    return templates.TemplateResponse(request, name, base_context(request, user, **extra))
