"""Account settings."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.dependencies import render, require_password_changed
from app.models import User

router = APIRouter()


@router.get("/settings")
def settings_page(request: Request, user: User = Depends(require_password_changed)):
    return render(request, "settings/settings.html", user)
