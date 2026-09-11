"""Theme and density (how big the whole site feels)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import THEMES, DENSITIES, LIST_VIEWS, get_current_user
from app.models import User

router = APIRouter()


def _save_cookie(resp: RedirectResponse, request: Request, name: str, value: str) -> None:
    resp.set_cookie(
        name,
        value,
        max_age=60 * 60 * 24 * 365,
        samesite="lax",
        secure=settings.secure_cookie_for(request),
    )


@router.post("/theme")
def set_look(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
    theme: str = Form(""),
    density: str = Form(""),
    next: str = Form("/"),
):
    current_theme = (user.theme_preference if user else request.cookies.get("aa_theme")) or "ascendancy"
    current_density = (getattr(user, "density_preference", None) if user else request.cookies.get("aa_density")) or "cozy"
    chosen_theme = theme.strip().lower()
    chosen_density = density.strip().lower()
    if chosen_theme == "cycle":
        idx = THEMES.index(current_theme) if current_theme in THEMES else 0
        chosen_theme = THEMES[(idx + 1) % len(THEMES)]
    if chosen_theme not in THEMES:
        chosen_theme = current_theme if current_theme in THEMES else "ascendancy"
    if chosen_density not in DENSITIES:
        chosen_density = current_density if current_density in DENSITIES else "cozy"
    if user:
        user.theme_preference = chosen_theme
        user.density_preference = chosen_density
        db.add(user)
        db.commit()
    dest = next if next.startswith("/") else "/"
    resp = RedirectResponse(dest, status_code=303)
    _save_cookie(resp, request, "aa_theme", chosen_theme)
    _save_cookie(resp, request, "aa_density", chosen_density)
    return resp


@router.post("/view")
def set_list_view(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user),
    view: str = Form("cards"),
    next: str = Form("/"),
):
    chosen = view.strip().lower()
    if chosen not in LIST_VIEWS:
        chosen = "cards"
    if user:
        user.list_view_preference = chosen
        db.add(user)
        db.commit()
    dest = next if next.startswith("/") else "/"
    resp = RedirectResponse(dest, status_code=303)
    _save_cookie(resp, request, "aa_view", chosen)
    return resp
