"""Compose a reminder email from live unchecked items."""
from __future__ import annotations

import hashlib
import hmac
import html as _html
import re
from html.parser import HTMLParser

from sqlalchemy.orm import Session

from app.config import settings
from app.models import CalendarEvent, NoteBox, NotePage, ReminderJob, Task, User
from app.services.text import html_to_plain
from app.services.visibility import can_see_page, can_see_task


def _site(path: str) -> str:
    return f"{settings.site_url.rstrip('/')}{path}"


def stop_token(reminder_id: int) -> str:
    raw = f"reminder-stop:{reminder_id}".encode("utf-8")
    return hmac.new(settings.secret_key.encode("utf-8"), raw, hashlib.sha256).hexdigest()[:32]


def verify_stop_token(reminder_id: int, token: str) -> bool:
    if not token:
        return False
    return hmac.compare_digest(stop_token(reminder_id), token.strip())


def stop_url(reminder_id: int) -> str:
    return _site(f"/reminders/stop?id={reminder_id}&token={stop_token(reminder_id)}")


def unchecked_lines_from_html(raw: str) -> list[str]:
    """Pull still-open checkbox labels out of note HTML. Checked items are skipped."""

    class Checks(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.stack: list[dict] = []
            self.items: list[dict] = []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "li":
                checked = str(attrs.get("data-checked") or "").lower() == "true"
                is_task = str(attrs.get("data-type") or "") == "taskItem" or checked or "data-checked" in attrs
                row = {"text": [], "open": not checked, "box": is_task}
                self.stack.append(row)
                self.items.append(row)
            elif tag == "input" and attrs.get("type", "").lower() == "checkbox" and self.stack:
                self.stack[-1]["box"] = True
                checked = "checked" in attrs or str(attrs.get("checked") or "").lower() in {"", "checked", "true"}
                if "checked" not in attrs and str(attrs.get("checked") or "").lower() not in {"checked", "true", ""}:
                    checked = False
                if "checked" in attrs:
                    checked = True
                elif str(attrs.get("data-checked") or "").lower() == "true":
                    checked = True
                else:
                    checked = False
                self.stack[-1]["open"] = not checked
            elif tag == "br" and self.stack:
                self.stack[-1]["text"].append(" ")

        def handle_endtag(self, tag):
            if tag == "li" and self.stack:
                self.stack.pop()

        def handle_data(self, text):
            if self.stack:
                self.stack[-1]["text"].append(text)

    parser = Checks()
    parser.feed(raw or "")
    out = []
    for row in parser.items:
        if not row.get("box") or not row.get("open"):
            continue
        text = re.sub(r"\s+", " ", "".join(row["text"])).strip()
        if text:
            out.append(text)
    return out


def item_allowed(db: Session, user: User | None, item_type: str, item_id: int | None) -> bool:
    if item_type == "text":
        return True
    if not user:
        return False
    if item_type == "task":
        task = db.get(Task, item_id) if item_id else None
        return bool(task and can_see_task(db, user, task))
    if item_type == "page":
        page = db.get(NotePage, item_id) if item_id else None
        return bool(page and can_see_page(db, user, page))
    if item_type == "container":
        box = db.get(NoteBox, item_id) if item_id else None
        page = db.get(NotePage, box.page_id) if box else None
        return bool(page and can_see_page(db, user, page))
    if item_type == "event":
        ev = db.get(CalendarEvent, item_id) if item_id else None
        return bool(ev and not ev.deleted_at)
    return False


def _label_for(db: Session, item) -> dict | None:
    t = item.item_type
    if t == "text":
        return {"title": item.text or "", "lines": [], "url": None}

    if t == "task":
        task = db.get(Task, item.item_id) if item.item_id else None
        if not task or task.deleted_at or task.completed:
            return None
        due = f" (due {task.due_at.strftime('%b %d %H:%M')})" if task.due_at else ""
        return {"title": f"[ ] {task.title}{due}", "lines": [], "url": _site("/tasks")}

    if t in {"page", "container"}:
        box = db.get(NoteBox, item.item_id) if t == "container" and item.item_id else None
        page = db.get(NotePage, box.page_id if box else item.item_id) if item.item_id and (t == "page" or box) else None
        if not page or page.deleted_at:
            return None
        html = (box.body_html if box else page.body_html) or ""
        open_items = unchecked_lines_from_html(html)
        page_url = _site(f"/notes/{page.id}")
        if open_items:
            return {"title": f"Note: {page.title}", "lines": open_items, "url": page_url}
        if re.search(r"type=['\"]checkbox['\"]|data-type=['\"]taskItem['\"]|data-checked=", html, flags=re.I):
            return None
        preview = (page.body_plain or html_to_plain(html)).strip().replace("\n", " ")
        if len(preview) > 160:
            preview = preview[:160] + "…"
        lines = [preview] if preview else []
        return {"title": f"Note: {page.title}", "lines": lines, "url": page_url}

    if t == "event":
        ev = db.get(CalendarEvent, item.item_id) if item.item_id else None
        if not ev or ev.deleted_at:
            return None
        when = ev.starts_at.strftime("%a %b %d %H:%M") if ev.starts_at else ""
        return {"title": f"Event: {ev.title} — {when}", "lines": [], "url": _site("/calendar")}

    return None


def compose(db: Session, reminder: ReminderJob) -> dict:
    subject = (reminder.name or reminder.subject or "Reminder").strip()
    off = stop_url(reminder.id)
    user = db.get(User, reminder.user_id)

    parts = [
        _label_for(db, it)
        for it in reminder.items
        if item_allowed(db, user, it.item_type, it.item_id)
    ]
    parts = [p for p in parts if p]

    if not parts:
        text = reminder.body or reminder.subject or subject
        if reminder.items:
            text = f"{subject}\n\nAll caught up — nothing left unchecked."
        text = f"{text}\n\nTurn this reminder off: {off}"
        html = (
            f"<p>{_html.escape(text.split(chr(10)+chr(10))[0])}</p>"
            f"<p><a href='{off}'>Turn this reminder off</a></p>"
            f"<p style='color:#888'>— Ascendancy Academy</p>"
        )
        sms = f"AA: {subject}\n{_site('/reminders')}\nOff: {off}"
        return {"subject": subject, "text": text, "html": html, "sms": sms}

    text_lines = [subject, ""]
    for p in parts:
        text_lines.append(f"• {p['title']}")
        for ln in p["lines"]:
            text_lines.append(f"    {ln}")
        if p["url"]:
            text_lines.append(f"    {p['url']}")
    text_lines += ["", f"Turn this reminder off: {off}", "", "— Ascendancy Academy"]
    text = "\n".join(text_lines)

    html_parts = [f"<h2 style='margin:0 0 12px'>{_html.escape(subject)}</h2><ul>"]
    for p in parts:
        title = _html.escape(p["title"])
        if p["url"]:
            title = f"<a href='{p['url']}'>{title}</a>"
        html_parts.append(f"<li style='margin:6px 0'>{title}")
        if p["lines"]:
            html_parts.append("<ul>")
            for ln in p["lines"]:
                html_parts.append(f"<li>{_html.escape(ln)}</li>")
            html_parts.append("</ul>")
        html_parts.append("</li>")
    html_parts.append(
        "</ul>"
        f"<p><a href='{off}'>Turn this reminder off</a></p>"
        "<p style='color:#888'>— Ascendancy Academy</p>"
    )
    sms_lines = [f"AA: {subject}"]
    for p in parts:
        if p["url"]:
            sms_lines.append(p["url"])
        else:
            sms_lines.append(p["title"][:60])
    sms_lines.append(f"Off: {off}")
    return {"subject": subject, "text": text, "html": "".join(html_parts), "sms": "\n".join(sms_lines)}
