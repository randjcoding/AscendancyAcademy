"""Teacher view of AI spend."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import first_student, render, require_teacher
from app.models import User
from app.services import ai_usage as usage_svc

router = APIRouter()


@router.get("/usage")
def usage_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    student = first_student(db)
    rows = usage_svc.month_rows(db)
    names = {}
    for row in rows:
        if row.user_id not in names:
            owner = db.get(User, row.user_id)
            names[row.user_id] = owner.full_name if owner else "Teacher"
    return render(
        request,
        "teacher/usage.html",
        user,
        _db=db,
        student=student,
        rows=rows,
        names=names,
        month_total=usage_svc.month_total(db),
        month_label=datetime.utcnow().strftime("%B %Y"),
    )
