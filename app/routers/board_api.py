"""Due-today board: assignments, tasks, calendar days, and reminders."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Assignment, CalendarEvent, Course, ReminderJob, ReminderStatus
from app.routers.api import _must_user
from app.services.clock import house_today
from app.services.visibility import can_complete_task, class_ids_for, visible_tasks

router = APIRouter(prefix="/api/board")


@router.get("/today")
def board_today(request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    today = house_today()
    start = datetime.combine(today, datetime.min.time())
    end = start + timedelta(days=1)
    course_ids = class_ids_for(db, user)
    if user.is_teacher:
        course_ids = set(db.scalars(select(Course.id)).all())

    items: list[dict] = []

    asg_q = select(Assignment).where(
        Assignment.due_date.is_not(None),
        Assignment.due_date <= today,
    )
    if user.is_student:
        if not course_ids:
            asg_q = asg_q.where(Assignment.id == -1)
        else:
            asg_q = asg_q.where(Assignment.course_id.in_(course_ids))
    for asg in db.scalars(asg_q.order_by(Assignment.due_date, Assignment.id)).all():
        course = db.get(Course, asg.course_id)
        late = bool(asg.due_date and asg.due_date < today)
        items.append(
            {
                "kind": "assignment",
                "id": asg.id,
                "title": asg.title,
                "subtitle": course.title if course else "Class",
                "due": asg.due_date.isoformat() if asg.due_date else today.isoformat(),
                "late": late,
                "href": f"/courses/{asg.course_id}" if user.is_teacher else "/grades",
                "task_id": None,
            }
        )

    for task in visible_tasks(db, user):
        if task.completed or not task.due_at:
            continue
        due_d = task.due_at.date()
        if due_d > today:
            continue
        items.append(
            {
                "kind": "task",
                "id": task.id,
                "title": task.title,
                "subtitle": "To-do",
                "due": due_d.isoformat(),
                "late": due_d < today,
                "href": "/tasks",
                "task_id": task.id,
                "can_complete": can_complete_task(db, user, task),
            }
        )

    events = db.scalars(
        select(CalendarEvent).where(
            CalendarEvent.deleted_at.is_(None),
            CalendarEvent.starts_at >= start,
            CalendarEvent.starts_at < end,
        )
    ).all()
    for ev in events:
        items.append(
            {
                "kind": "event",
                "id": ev.id,
                "title": ev.title,
                "subtitle": "Calendar",
                "due": today.isoformat(),
                "late": False,
                "href": "/calendar",
                "task_id": None,
            }
        )

    reminders = db.scalars(
        select(ReminderJob).where(
            ReminderJob.status == ReminderStatus.PENDING,
            ReminderJob.send_at >= start,
            ReminderJob.send_at < end,
        )
    ).all()
    for job in reminders:
        if job.user_id != user.id and job.audience != "family":
            continue
        items.append(
            {
                "kind": "reminder",
                "id": job.id,
                "title": job.name or job.subject or "Reminder",
                "subtitle": "Reminder",
                "due": today.isoformat(),
                "late": False,
                "href": "/reminders",
                "task_id": None,
            }
        )

    late = [i for i in items if i["late"]]
    due = [i for i in items if not i["late"]]
    return {"today": today.isoformat(), "late": late, "due": due, "items": late + due}
