"""Teacher and student login doors."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import base_context, get_current_user, render, session_token, templates
from app.models import User, UserKind
from app.security import (
    FAILURE_MESSAGE,
    authenticate,
    create_session,
    delete_all_sessions,
    delete_session,
    hash_password,
    verify_csrf,
    verify_password,
)
from app.services.turnstile import (
    FAILURE_MESSAGE as TURNSTILE_FAILURE,
    turnstile_token_from_request,
    verify_turnstile,
)

router = APIRouter(tags=["auth"])

WRONG_DOOR = {
    UserKind.TEACHER: "This is the student door. Teachers sign in next door.",
    UserKind.STUDENT: "This is the teacher door. Students sign in next door.",
}


def _set_session_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.secure_cookie_for(request),
        max_age=settings.session_ttl_hours * 3600,
        domain=settings.cookie_domain or None,
    )


def _clear_session_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        domain=settings.cookie_domain or None,
        secure=settings.secure_cookie_for(request),
    )


def _home_for(user: User) -> str:
    return "/teacher" if user.kind == UserKind.TEACHER else "/activities"


@router.get("/login")
def login_chooser(request: Request, user: User | None = Depends(get_current_user)):
    if user and not user.must_change_password:
        return RedirectResponse(_home_for(user), status_code=303)
    if user and user.must_change_password:
        return RedirectResponse("/settings/password?forced=1", status_code=303)
    return render(request, "auth/choose.html", user)


@router.get("/login/{door}")
def login_page(
    door: str,
    request: Request,
    user: User | None = Depends(get_current_user),
):
    if door not in {"teacher", "student"}:
        return RedirectResponse("/login", status_code=303)
    if user and not user.must_change_password:
        return RedirectResponse(_home_for(user), status_code=303)
    expected = UserKind.TEACHER if door == "teacher" else UserKind.STUDENT
    return render(
        request,
        "auth/login.html",
        user,
        error=None,
        door=door,
        door_label="Teacher" if door == "teacher" else "Student",
        expected_kind=expected.value,
        next=request.query_params.get("next") or _default_next(door),
    )


def _default_next(door: str) -> str:
    return "/teacher" if door == "teacher" else "/student"


@router.post("/login/{door}")
async def login_submit(
    door: str,
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
):
    if door not in {"teacher", "student"}:
        return RedirectResponse("/login", status_code=303)
    expected = UserKind.TEACHER if door == "teacher" else UserKind.STUDENT
    ctx = dict(
        door=door,
        door_label="Teacher" if door == "teacher" else "Student",
        expected_kind=expected.value,
        next=next,
    )
    token = await turnstile_token_from_request(request)
    if not verify_turnstile(request, token):
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            base_context(request, None, error=TURNSTILE_FAILURE, **ctx),
            status_code=400,
        )
    user = authenticate(db, email, password, request)
    if not user:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            base_context(request, None, error=FAILURE_MESSAGE, **ctx),
            status_code=400,
        )
    if user.kind != expected:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            base_context(request, None, error=WRONG_DOOR[expected], **ctx),
            status_code=400,
        )
    session = create_session(db, user, request)
    dest = next if next.startswith("/") else _home_for(user)
    if user.must_change_password:
        dest = "/settings/password?forced=1"
    resp = RedirectResponse(dest, status_code=303)
    _set_session_cookie(resp, request, session)
    return resp


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    delete_session(db, session_token(request))
    resp = RedirectResponse("/login", status_code=303)
    _clear_session_cookie(resp, request)
    return resp


@router.get("/settings/password")
def password_page(
    request: Request,
    user: User | None = Depends(get_current_user),
    forced: int = 0,
):
    if not user:
        return RedirectResponse("/login", status_code=303)
    return render(
        request,
        "auth/password.html",
        user,
        error=None,
        forced=bool(forced),
        ok=False,
    )


@router.post("/settings/password")
def password_submit(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
    current_password: str = Form(""),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    csrf_token: str = Form(""),
    forced: int = Form(0),
):
    if not user:
        return RedirectResponse("/login", status_code=303)
    tok = session_token(request)
    if not verify_csrf(tok, csrf_token):
        return templates.TemplateResponse(
            request,
            "auth/password.html",
            base_context(
                request,
                user,
                error="That form expired. Refresh and try again.",
                forced=bool(forced),
                ok=False,
            ),
            status_code=400,
        )
    if len(new_password) < 10:
        return templates.TemplateResponse(
            request,
            "auth/password.html",
            base_context(
                request,
                user,
                error="Password must be at least 10 characters.",
                forced=bool(forced),
                ok=False,
            ),
            status_code=400,
        )
    if new_password != confirm_password:
        return templates.TemplateResponse(
            request,
            "auth/password.html",
            base_context(
                request,
                user,
                error="Passwords do not match.",
                forced=bool(forced),
                ok=False,
            ),
            status_code=400,
        )
    if not forced and user.password_hash and not verify_password(current_password, user.password_hash):
        return templates.TemplateResponse(
            request,
            "auth/password.html",
            base_context(
                request,
                user,
                error="Current password is incorrect.",
                forced=False,
                ok=False,
            ),
            status_code=400,
        )
    user.password_hash = hash_password(new_password)
    user.must_change_password = False
    db.add(user)
    delete_all_sessions(db, user.id)
    session = create_session(db, user, request)
    resp = RedirectResponse(_home_for(user), status_code=303)
    _set_session_cookie(resp, request, session)
    return resp
