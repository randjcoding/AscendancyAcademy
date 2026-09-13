"""Reminder jobs, send-now, cancel, and the one-click stop link."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import ReminderItem, ReminderJob, ReminderStatus, User
from app.routers.api import _csrf_bad, _err, _must_user
from app.services.clock import house_now
from app.services.dates import parse_due
from app.services.recurrence import apply_rule_to_job, describe_rule, rule_from_form, rule_from_job
from app.services.reminder_compose import verify_stop_token
from app.services.reminders import deliver_reminder

router = APIRouter(prefix="/api/reminders")
ITEM_TYPES = {"task", "page", "event", "text"}


class ItemIn(BaseModel):
    item_type: str
    item_id: int = 0
    text: str = ""


class ReminderBody(BaseModel):
    csrf: str = ""
    name: str = ""
    send_at: str = ""
    audience: str = "personal"
    repeat_kind: str = "none"
    repeat_until: str = ""
    repeat_days: list[str] = []
    items: list[ItemIn] = []


class CsrfBody(BaseModel):
    csrf: str = ""


def _parse_when(raw: str) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        if "T" in text:
            return datetime.fromisoformat(text[:19])
        if len(text) == 10:
            return datetime.fromisoformat(text + "T09:00:00")
    except ValueError:
        pass
    return parse_due(text)


def _job_json(job: ReminderJob) -> dict:
    rule = rule_from_job(job)
    return {
        "id": job.id,
        "name": job.name or job.subject or "Reminder",
        "send_at": job.send_at.isoformat(timespec="minutes") if job.send_at else "",
        "audience": job.audience or "personal",
        "status": job.status,
        "repeat": describe_rule(rule),
        "repeat_kind": job.recurrence or "none",
        "repeat_until": job.repeat_until.isoformat() if job.repeat_until else "",
        "items": [
            {"id": it.id, "item_type": it.item_type, "item_id": it.item_id, "text": it.text}
            for it in job.items
        ],
    }


def _apply_items(job: ReminderJob, items: list[ItemIn]) -> None:
    job.items.clear()
    for i, raw in enumerate(items):
        kind = (raw.item_type or "text").strip().lower()
        if kind not in ITEM_TYPES:
            continue
        job.items.append(
            ReminderItem(
                item_type=kind,
                item_id=raw.item_id or None,
                text=(raw.text or "")[:500],
                sort_order=i,
            )
        )


def _fill_job(job: ReminderJob, body: ReminderBody, user: User) -> str | None:
    when = _parse_when(body.send_at)
    if not when:
        return "Pick a time to send."
    name = body.name.strip() or "Reminder"
    job.name = name
    job.subject = name
    job.send_at = when
    job.audience = "family" if body.audience == "family" and user.is_teacher else "personal"
    job.recipient = user.email
    if not job.series_start:
        job.series_start = when
    rule = rule_from_form(
        repeat_kind=body.repeat_kind,
        repeat_until=body.repeat_until,
        repeat_days=body.repeat_days,
        starts=when,
    )
    apply_rule_to_job(job, rule)
    _apply_items(job, body.items)
    job.status = ReminderStatus.PENDING
    return None


@router.get("/")
def list_reminders(request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    q = select(ReminderJob).where(ReminderJob.status != ReminderStatus.CANCELLED)
    if not user.is_teacher:
        q = q.where(ReminderJob.user_id == user.id)
    jobs = db.scalars(q.order_by(ReminderJob.send_at.desc())).all()
    if user.is_teacher:
        jobs = [j for j in jobs if j.user_id == user.id or j.audience == "family"]
    return {"reminders": [_job_json(j) for j in jobs], "can_family": user.is_teacher}


@router.post("/")
def create_reminder(body: ReminderBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    job = ReminderJob(user_id=user.id, send_at=house_now(), recipient=user.email)
    err = _fill_job(job, body, user)
    if err:
        return _err(err)
    db.add(job)
    db.commit()
    db.refresh(job)
    return {"ok": True, "reminder": _job_json(job)}


@router.post("/{job_id}")
def update_reminder(job_id: int, body: ReminderBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    job = db.get(ReminderJob, job_id)
    if not job or job.user_id != user.id:
        return _err("That reminder is gone.", 404)
    err = _fill_job(job, body, user)
    if err:
        return _err(err)
    db.commit()
    db.refresh(job)
    return {"ok": True, "reminder": _job_json(job)}


@router.post("/{job_id}/send-now")
def send_now(job_id: int, body: CsrfBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    job = db.get(ReminderJob, job_id)
    if not job or job.user_id != user.id:
        return _err("That reminder is gone.", 404)
    ok = deliver_reminder(db, job, user, force=True)
    if not ok:
        return _err("Could not send that email.")
    db.commit()
    return {"ok": True}


@router.post("/{job_id}/cancel")
def cancel_reminder(job_id: int, body: CsrfBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    job = db.get(ReminderJob, job_id)
    if not job or job.user_id != user.id:
        return _err("That reminder is gone.", 404)
    job.status = ReminderStatus.CANCELLED
    db.commit()
    return {"ok": True}


@router.get("/stop")
def stop_reminder(id: int = 0, token: str = "", db: Session = Depends(get_db)):
    job = db.get(ReminderJob, id)
    if not job or not verify_stop_token(id, token):
        return _err("That stop link is not valid.", 403)
    job.status = ReminderStatus.CANCELLED
    db.commit()
    return RedirectResponse("/reminders?stopped=1", status_code=303)


@router.post("/internal/run")
def run_due(request: Request, db: Session = Depends(get_db)):
    token = request.headers.get("x-job-token") or request.query_params.get("token") or ""
    if not settings.reminder_job_token or token != settings.reminder_job_token:
        return _err("Forbidden", 403)
    from app.services.reminders import process_due_reminders

    sent = process_due_reminders(db)
    return {"ok": True, "sent": sent}
