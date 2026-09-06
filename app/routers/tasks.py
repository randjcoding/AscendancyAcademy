"""Simple household / school tasks."""
from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import first_student, render, require_login, require_teacher, session_token, student_profile
from app.models import Task, User, UserKind
from app.security import verify_csrf

router = APIRouter()


@router.get("/tasks")
def task_list(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    if user.must_change_password:
        return RedirectResponse("/settings/password?forced=1", status_code=303)
    student = student_profile(db, user) if user.kind == UserKind.STUDENT else first_student(db)
    tasks = db.scalars(
        select(Task)
        .where(Task.deleted_at.is_(None))
        .order_by(Task.completed.asc(), Task.due_at.asc(), Task.id.desc())
    ).all()
    return render(
        request,
        "tasks/tasks.html",
        user,
        _db=db,
        student=student,
        tasks=tasks,
        can_edit=user.kind == UserKind.TEACHER,
        today=date.today(),
    )


@router.post("/tasks")
def create_task(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
    csrf_token: str = Form(""),
    title: str = Form(...),
    due_date: str = Form(""),
    notes: str = Form(""),
    show_on_calendar: str = Form(""),
):
    if not verify_csrf(session_token(request), csrf_token):
        return RedirectResponse("/tasks", status_code=303)
    name = title.strip()
    if not name:
        return RedirectResponse("/tasks", status_code=303)
    due_at = None
    if due_date.strip():
        try:
            due_at = datetime.combine(date.fromisoformat(due_date.strip()), datetime.min.time())
        except ValueError:
            return RedirectResponse("/tasks", status_code=303)
    student = first_student(db)
    db.add(
        Task(
            created_by_user_id=user.id,
            student_id=student.id if student else None,
            title=name,
            notes=notes.strip(),
            due_at=due_at,
            show_on_calendar=bool(show_on_calendar) if show_on_calendar != "" else True,
        )
    )
    db.commit()
    return RedirectResponse("/tasks", status_code=303)


@router.post("/tasks/{task_id}/toggle")
def toggle_task(
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
    csrf_token: str = Form(""),
):
    if not verify_csrf(session_token(request), csrf_token):
        return RedirectResponse("/tasks", status_code=303)
    task = db.get(Task, task_id)
    if task and not task.deleted_at:
        task.completed = not task.completed
        db.commit()
    return RedirectResponse("/tasks", status_code=303)


@router.post("/tasks/{task_id}/delete")
def delete_task(
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
    csrf_token: str = Form(""),
):
    if not verify_csrf(session_token(request), csrf_token):
        return RedirectResponse("/tasks", status_code=303)
    task = db.get(Task, task_id)
    if task:
        task.deleted_at = datetime.utcnow()
        db.commit()
    return RedirectResponse("/tasks", status_code=303)
