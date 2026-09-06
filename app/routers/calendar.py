"""School calendar: events, assignment due dates, and tasks."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import first_student, render, require_login, require_teacher, session_token, student_profile
from app.models import Assignment, CalendarEvent, Course, Enrollment, Task, User, UserKind
from app.security import verify_csrf

router = APIRouter()


def _parse_iso(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1]
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is not None:
            parsed = parsed.replace(tzinfo=None)
        return parsed
    except ValueError:
        return None


@router.get("/calendar")
def calendar_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
):
    if user.must_change_password:
        return RedirectResponse("/settings/password?forced=1", status_code=303)
    student = student_profile(db, user) if user.kind == UserKind.STUDENT else first_student(db)
    return render(
        request,
        "calendar/calendar.html",
        user,
        _db=db,
        student=student,
        can_edit=user.kind == UserKind.TEACHER,
    )


@router.get("/api/calendar/events")
def api_events(
    db: Session = Depends(get_db),
    user: User = Depends(require_login),
    start: str = "",
    end: str = "",
):
    if user.must_change_password:
        return JSONResponse({"error": "password required"}, status_code=403)
    start_at = _parse_iso(start) or datetime.utcnow() - timedelta(days=45)
    end_at = _parse_iso(end) or datetime.utcnow() + timedelta(days=90)
    student = student_profile(db, user) if user.kind == UserKind.STUDENT else first_student(db)
    out = []

    events = db.scalars(
        select(CalendarEvent).where(
            CalendarEvent.deleted_at.is_(None),
            CalendarEvent.starts_at >= start_at - timedelta(days=1),
            CalendarEvent.starts_at <= end_at + timedelta(days=1),
        )
    ).all()
    for ev in events:
        if ev.assignment_id:
            continue
        out.append(
            {
                "id": f"event-{ev.id}",
                "title": ev.title,
                "start": ev.starts_at.date().isoformat() if ev.all_day else ev.starts_at.isoformat(timespec="seconds"),
                "end": ev.ends_at.date().isoformat() if ev.ends_at and ev.all_day else (
                    ev.ends_at.isoformat(timespec="seconds") if ev.ends_at else None
                ),
                "allDay": ev.all_day,
                "color": "#1D3557",
                "extendedProps": {
                    "kind": "event",
                    "db_id": ev.id,
                    "description": ev.description or "",
                },
            }
        )

    assignment_q = select(Assignment).where(
        Assignment.show_on_calendar.is_(True),
        Assignment.due_date.is_not(None),
        Assignment.due_date >= start_at.date(),
        Assignment.due_date <= end_at.date(),
    )
    if student:
        assignment_q = (
            assignment_q.join(Course)
            .join(Enrollment)
            .where(Enrollment.student_id == student.id)
        )
    for assignment in db.scalars(assignment_q).unique().all():
        out.append(
            {
                "id": f"assignment-{assignment.id}",
                "title": f"{assignment.course.title}: {assignment.title}",
                "start": assignment.due_date.isoformat(),
                "allDay": True,
                "color": assignment.course.color or "#2D6A4F",
                "extendedProps": {
                    "kind": "assignment",
                    "db_id": assignment.id,
                    "description": assignment.description or "",
                    "href": f"/courses/{assignment.course_id}" if user.kind == UserKind.TEACHER else "/grades",
                },
            }
        )

    tasks = db.scalars(
        select(Task).where(
            Task.deleted_at.is_(None),
            Task.show_on_calendar.is_(True),
            Task.due_at.is_not(None),
            Task.due_at >= start_at - timedelta(days=1),
            Task.due_at <= end_at + timedelta(days=1),
        )
    ).all()
    for task in tasks:
        out.append(
            {
                "id": f"task-{task.id}",
                "title": task.title,
                "start": task.due_at.date().isoformat(),
                "allDay": True,
                "color": "#B45309" if not task.completed else "#6B7280",
                "extendedProps": {
                    "kind": "task",
                    "db_id": task.id,
                    "description": task.notes or "",
                    "completed": task.completed,
                },
            }
        )
    return JSONResponse(out)


@router.post("/calendar/events")
def create_event(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
    csrf_token: str = Form(""),
    title: str = Form(...),
    on_date: str = Form(...),
    description: str = Form(""),
):
    if not verify_csrf(session_token(request), csrf_token):
        return RedirectResponse("/calendar", status_code=303)
    name = title.strip()
    try:
        day = date.fromisoformat(on_date)
    except ValueError:
        return RedirectResponse("/calendar", status_code=303)
    if not name:
        return RedirectResponse("/calendar", status_code=303)
    student = first_student(db)
    db.add(
        CalendarEvent(
            created_by_user_id=user.id,
            student_id=student.id if student else None,
            title=name,
            description=description.strip(),
            starts_at=datetime.combine(day, datetime.min.time()),
            all_day=True,
        )
    )
    db.commit()
    return RedirectResponse("/calendar", status_code=303)


@router.post("/calendar/events/{event_id}/delete")
def delete_event(
    event_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
    csrf_token: str = Form(""),
):
    if not verify_csrf(session_token(request), csrf_token):
        return RedirectResponse("/calendar", status_code=303)
    event = db.get(CalendarEvent, event_id)
    if event:
        event.deleted_at = datetime.utcnow()
        db.commit()
    return RedirectResponse("/calendar", status_code=303)
