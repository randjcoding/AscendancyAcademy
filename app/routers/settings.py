"""Account settings and named API keys."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import render, require_password_changed, require_teacher, session_token
from app.models import TeacherApiKey, User
from app.security import verify_csrf
from app.services.secrets import encrypt_secret

router = APIRouter()

PROVIDERS = (("openai", "OpenAI"), ("anthropic", "Anthropic"))


@router.get("/settings")
def settings_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_password_changed),
):
    keys = []
    if user.is_teacher:
        keys = db.scalars(
            select(TeacherApiKey)
            .where(TeacherApiKey.user_id == user.id)
            .order_by(TeacherApiKey.name.asc())
        ).all()
    return render(
        request,
        "settings/settings.html",
        user,
        keys=keys,
        providers=PROVIDERS,
        error=request.query_params.get("error", ""),
        ok=request.query_params.get("ok", ""),
    )


@router.post("/settings/keys")
def add_key(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
    csrf_token: str = Form(""),
    name: str = Form(""),
    provider: str = Form("openai"),
    secret: str = Form(""),
):
    if not verify_csrf(session_token(request), csrf_token):
        return RedirectResponse("/settings?error=That+form+expired.", status_code=303)
    label = name.strip() or provider.title()
    raw = secret.strip()
    if not raw:
        return RedirectResponse("/settings?error=Paste+the+secret+key.", status_code=303)
    if provider not in {p for p, _ in PROVIDERS}:
        return RedirectResponse("/settings?error=Pick+OpenAI+or+Anthropic.", status_code=303)
    db.add(
        TeacherApiKey(
            user_id=user.id,
            name=label,
            provider=provider,
            secret_enc=encrypt_secret(raw),
        )
    )
    db.commit()
    return RedirectResponse("/settings?ok=Key+saved.", status_code=303)


@router.post("/settings/keys/{key_id}/delete")
def delete_key(
    key_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
    csrf_token: str = Form(""),
):
    if not verify_csrf(session_token(request), csrf_token):
        return RedirectResponse("/settings?error=That+form+expired.", status_code=303)
    row = db.get(TeacherApiKey, key_id)
    if row and row.user_id == user.id:
        db.delete(row)
        db.commit()
    return RedirectResponse("/settings?ok=Key+removed.", status_code=303)
