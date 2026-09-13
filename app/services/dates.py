"""Parse natural-ish date/time shortcuts on the house clock."""
from __future__ import annotations

import re
from datetime import datetime, time, timedelta

from dateutil import parser as date_parser

from app.services.clock import house_now

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DEFAULT_HOUR = 9


def _parse_time(text: str) -> time | None:
    t = text.strip().lower().replace("at ", " ").strip()
    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", t)
    if m:
        hour = int(m.group(1)) % 12
        minute = int(m.group(2) or 0)
        if m.group(3) == "pm":
            hour += 12
        return time(hour % 24, minute)
    m = re.search(r"\b(\d{1,2}):(\d{2})\b", t)
    if m:
        return time(int(m.group(1)) % 24, int(m.group(2)) % 60)
    return None


def _apply_time(d: datetime, tod: time | None) -> datetime:
    if tod is None:
        return d.replace(hour=DEFAULT_HOUR, minute=0, second=0, microsecond=0)
    return d.replace(hour=tod.hour, minute=tod.minute, second=0, microsecond=0)


def parse_due(text: str) -> datetime | None:
    raw = (text or "").strip().lower()
    if not raw:
        return None
    now = house_now()
    tod = _parse_time(raw)

    m = re.search(
        r"\bin\s+(\d+)\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days|w|week|weeks)\b",
        raw,
    )
    if m:
        n = int(m.group(1))
        unit = m.group(2)[0]
        if unit == "m":
            return now + timedelta(minutes=n)
        if unit == "h":
            return now + timedelta(hours=n)
        if unit == "w":
            return now + timedelta(weeks=n)
        return now + timedelta(days=n)

    if re.match(r"^(today|tod)\b", raw):
        return _apply_time(now, tod)
    if re.match(r"^(tomorrow|tmr|tom)\b", raw):
        return _apply_time(now + timedelta(days=1), tod)

    wd_text = raw
    force_next = False
    if wd_text.startswith("next "):
        force_next = True
        wd_text = wd_text[5:]
    for i, name in enumerate(WEEKDAYS):
        if wd_text == name or wd_text.startswith(name[:3] + " ") or wd_text == name[:3]:
            days_ahead = (i - now.weekday()) % 7
            if days_ahead == 0 or force_next:
                days_ahead = days_ahead or 7
                if force_next and days_ahead == 0:
                    days_ahead = 7
            target = now + timedelta(days=days_ahead)
            return _apply_time(target, tod)

    if tod is not None and re.match(r"^(at\s+)?\d{1,2}(:\d{2})?\s*(am|pm)?$", raw):
        candidate = _apply_time(now, tod)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    try:
        parsed = date_parser.parse(
            text,
            fuzzy=True,
            default=now.replace(hour=DEFAULT_HOUR, minute=0, second=0, microsecond=0),
        )
        return parsed
    except (ValueError, TypeError, OverflowError):
        return None
