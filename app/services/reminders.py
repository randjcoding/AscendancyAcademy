"""Due reminder processing (email and SMS)."""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AccountStatus, ReminderJob, ReminderStatus, User
from app.services.clock import house_now
from app.services.email import send_email
from app.services.recurrence import next_occurrence, rule_from_job
from app.services.reminder_compose import compose
from app.services.sms import send_sms

logger = logging.getLogger("aa.reminders")
VALID_CHANNELS = {"email", "sms", "both"}


def normalize_channel(raw: str | None) -> str:
    channel = (raw or "email").lower().strip()
    return channel if channel in VALID_CHANNELS else "email"


def family_emails(db: Session) -> list[str]:
    rows = db.scalars(select(User).where(User.status == AccountStatus.ACTIVE)).all()
    return [u.email for u in rows if (u.email or "").strip()]


def family_phones(db: Session) -> list[str]:
    rows = db.scalars(select(User).where(User.status == AccountStatus.ACTIVE)).all()
    return [u.phone for u in rows if (getattr(u, "phone", None) or "").strip()]


def _email_recipients(db: Session, job: ReminderJob, user: User | None) -> list[str]:
    if (job.audience or "personal") == "family":
        return family_emails(db)
    dest = (job.recipient or (user.email if user else "") or "").strip()
    return [dest] if dest else []


def _sms_dest(db: Session, job: ReminderJob, user: User | None) -> str:
    if (job.audience or "personal") == "family":
        phones = family_phones(db)
        return phones[0] if phones else (job.sms_to or "")
    return (job.sms_to or (user.phone if user else "") or "").strip()


def _next_send(job: ReminderJob):
    rule = rule_from_job(job)
    if not rule:
        return None
    start = job.series_start or job.send_at
    return next_occurrence(start, rule, job.send_at)


def deliver_reminder(db: Session, job: ReminderJob, user: User | None, *, force: bool = False) -> bool:
    message = compose(db, job)
    channel = normalize_channel(job.channel)
    ok = True
    if channel in {"email", "both"} and (force or job.email_delivered_for != job.send_at):
        recipients = _email_recipients(db, job, user)
        if not recipients:
            ok = False
        else:
            delivered = send_email(
                to=recipients,
                subject=message["subject"],
                text_body=message["text"],
                html_body=message["html"],
            )
            if delivered and not force:
                job.email_delivered_for = job.send_at
                db.add(job)
                db.flush()
            ok = delivered and ok
    if channel in {"sms", "both"} and (force or job.sms_delivered_for != job.send_at):
        dest = _sms_dest(db, job, user)
        delivered = send_sms(to=dest, body=message.get("sms") or message["text"])
        if delivered and not force:
            job.sms_delivered_for = job.send_at
            db.add(job)
            db.flush()
        ok = delivered and ok
    return ok


def process_due_reminders(db: Session) -> int:
    now = house_now()
    due = db.scalars(
        select(ReminderJob.id).where(
            ReminderJob.status == ReminderStatus.PENDING,
            ReminderJob.send_at <= now,
        )
    ).all()
    sent = 0
    for job_id in due:
        q = select(ReminderJob).where(
            ReminderJob.id == job_id,
            ReminderJob.status == ReminderStatus.PENDING,
            ReminderJob.send_at <= now,
        )
        try:
            job = db.scalar(q.with_for_update(skip_locked=True))
        except Exception:
            job = db.get(ReminderJob, job_id)
            if not job or job.status != ReminderStatus.PENDING or job.send_at > now:
                continue
        if not job:
            continue
        user = db.get(User, job.user_id)
        if deliver_reminder(db, job, user):
            sent += 1
            job.last_sent_at = now
            nxt = _next_send(job)
            if nxt:
                job.send_at = nxt
                job.status = ReminderStatus.PENDING
            else:
                job.status = ReminderStatus.SENT
            db.add(job)
        else:
            logger.warning("Reminder %s failed to send", job.id)
        db.commit()
    db.commit()
    return sent
