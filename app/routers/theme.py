"""Theme preference."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User

router = APIRouter()
ALLOWED = {"light", "dark", "contrast", "academy"}
CYCLE = ["academy", "light", "dark", "contrast"]


@router.post("/theme")
def set_theme(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
    theme: str = Form(""),
    next: str = Form("/"),
):
    current = (user.theme_preference if user else request.cookies.get("aa_theme")) or "academy"
    chosen = theme.strip().lower()
    if chosen == "cycle":
        idx = CYCLE.index(current) if current in CYCLE else 0
        chosen = CYCLE[(idx + 1) % len(CYCLE)]
    if chosen not in ALLOWED:
        chosen = "academy"
    if user:
        user.theme_preference = chosen
        db.add(user)
        db.commit()
    dest = next if next.startswith("/") else "/"
    resp = RedirectResponse(dest, status_code=303)
    resp.set_cookie(
        "aa_theme",
        chosen,
        max_age=60 * 60 * 24 * 365,
        samesite="lax",
        secure=settings.secure_cookie_for(request),
    )
    return resp
