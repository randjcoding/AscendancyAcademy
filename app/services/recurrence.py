"""Repeat rules ported from OLDCCASITE, plus daily and optional until."""
from __future__ import annotations

import json
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any

from app.models import ReminderJob, ReminderStatus
from app.services.clock import house_now

WEEKDAY_CODES = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
WEEKDAY_LABELS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
NTH_LABELS = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", -1: "last"}
MAX_OCCURRENCES = 800
OPEN_DISPLAY_DAYS = 548


def weekday_code(d: date) -> str:
    return WEEKDAY_CODES[d.weekday()]


def parse_until(raw: str | date | None) -> date | None:
    if raw is None:
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    text = str(raw).strip()[:10]
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _nth_from_date(d: date) -> int:
    n = (d.day - 1) // 7 + 1
    return -1 if n >= 5 else n


def _parse_nth(raw: str, start_d: date) -> int:
    text = str(raw or "").strip().lower()
    if text in {"1", "2", "3", "4"}:
        return int(text)
    if text in {"-1", "5", "last"}:
        return -1
    return _nth_from_date(start_d)


def _nth_weekday(year: int, month: int, weekday: int, nth: int) -> date | None:
    if nth in {-1, 5}:
        last = monthrange(year, month)[1]
        d = date(year, month, last)
        d -= timedelta(days=(d.weekday() - weekday) % 7)
        return d
    nth = max(1, min(4, int(nth)))
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    day = 1 + offset + (nth - 1) * 7
    last = monthrange(year, month)[1]
    if day > last:
        return None
    return date(year, month, day)


def _add_months(year: int, month: int, n: int) -> tuple[int, int]:
    total = year * 12 + (month - 1) + n
    return total // 12, total % 12 + 1


def dump_rule(rule: dict[str, Any] | None) -> str:
    if not rule:
        return ""
    return json.dumps(rule, separators=(",", ":"))


def legacy_to_rule(raw: str, start: datetime | None = None, until: date | None = None) -> dict[str, Any] | None:
    kind = (raw or "").strip().lower()
    if kind in {"", "once", "none"}:
        return None
    start_d = (start or house_now()).date()
    until_s = until.isoformat() if until else ""
    if kind in {"hourly", "yearly"}:
        return {"freq": kind, "interval": 1, "until": until_s}
    if kind == "weekdays":
        return {"freq": "weekly", "interval": 1, "byweekday": list(WEEKDAY_CODES[:5]), "until": until_s}
    if kind == "daily":
        return {"freq": "daily", "interval": 1, "until": until_s}
    if kind == "weekly":
        return {"freq": "weekly", "interval": 1, "byweekday": [weekday_code(start_d)], "until": until_s}
    if kind == "biweekly":
        return {"freq": "weekly", "interval": 2, "byweekday": [weekday_code(start_d)], "until": until_s}
    if kind == "monthly":
        return {"freq": "monthly", "interval": 1, "monthly": "by_date", "until": until_s}
    if kind == "monthly_date":
        return {"freq": "monthly", "interval": 1, "monthly": "by_date", "until": until_s}
    if kind == "monthly_weekday":
        return {
            "freq": "monthly",
            "interval": 1,
            "monthly": "by_weekday",
            "nth": _nth_from_date(start_d),
            "byweekday": [weekday_code(start_d)],
            "until": until_s,
        }
    return None


def load_rule(raw: str | None, start: datetime | None = None, until: date | None = None) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        if until and not data.get("until"):
            data = dict(data)
            data["until"] = until.isoformat()
        return data
    return legacy_to_rule(text, start, until)


def rule_from_job(job: ReminderJob) -> dict[str, Any] | None:
    start = job.series_start or job.send_at
    until = job.repeat_until
    return load_rule(job.recurrence_json or job.recurrence, start, until)


def rule_from_form(
    *,
    repeat_kind: str = "",
    recurrence: str = "",
    repeat_until: str = "",
    repeat_days: list[str] | None = None,
    repeat_monthly_nth: str = "",
    repeat_monthly_weekday: str = "",
    starts: datetime | None = None,
) -> dict[str, Any] | None:
    kind = (repeat_kind or recurrence or "none").strip().lower()
    if kind in {"", "once", "none"}:
        return None
    starts = starts or house_now()
    start_d = starts.date()
    until = parse_until(repeat_until)
    days = [str(v).upper() for v in (repeat_days or []) if str(v).upper() in WEEKDAY_CODES]
    if kind == "daily":
        return {"freq": "daily", "interval": 1, "until": until.isoformat() if until else ""}
    if kind in {"weekly", "biweekly"}:
        return {
            "freq": "weekly",
            "interval": 2 if kind == "biweekly" else 1,
            "byweekday": days or [weekday_code(start_d)],
            "until": until.isoformat() if until else "",
        }
    if kind in {"monthly", "monthly_date"}:
        return {"freq": "monthly", "interval": 1, "monthly": "by_date", "until": until.isoformat() if until else ""}
    if kind == "monthly_weekday":
        nth = _parse_nth(repeat_monthly_nth, start_d)
        wd = str(repeat_monthly_weekday or "").strip().upper()
        if wd not in WEEKDAY_CODES:
            wd = weekday_code(start_d)
        return {
            "freq": "monthly",
            "interval": 1,
            "monthly": "by_weekday",
            "nth": nth,
            "byweekday": [wd],
            "until": until.isoformat() if until else "",
        }
    return legacy_to_rule(kind, starts, until)


def apply_rule_to_job(job: ReminderJob, rule: dict[str, Any] | None) -> None:
    job.recurrence_json = dump_rule(rule)
    if not rule:
        job.recurrence = ""
        job.repeat_until = None
        return
    freq = str(rule.get("freq") or "")
    interval = int(rule.get("interval") or 1)
    monthly = str(rule.get("monthly") or "")
    if freq == "daily":
        job.recurrence = "daily"
    elif freq == "weekly":
        job.recurrence = "biweekly" if interval == 2 else "weekly"
    elif freq == "monthly":
        job.recurrence = "monthly_weekday" if monthly == "by_weekday" else "monthly"
    else:
        job.recurrence = freq[:32]
    job.repeat_until = parse_until(rule.get("until"))
    if not job.series_start:
        job.series_start = job.send_at


def describe_rule(rule: dict[str, Any] | None) -> str:
    if not rule:
        return "Does not repeat"
    until = parse_until(rule.get("until"))
    until_txt = f" through {until.isoformat()}" if until else ""
    freq = rule.get("freq")
    if freq in {"hourly", "yearly"}:
        return f"Repeats every {'hour' if freq == 'hourly' else 'year'}{until_txt}"
    if freq == "daily":
        return f"Repeats every day{until_txt}"
    if freq == "weekly":
        interval = int(rule.get("interval") or 1)
        days = rule.get("byweekday") or []
        labels = [WEEKDAY_LABELS[WEEKDAY_CODES.index(c)] for c in days if c in WEEKDAY_CODES]
        day_txt = ", ".join(labels) if labels else "the same weekday"
        every = "every week" if interval == 1 else f"every {interval} weeks"
        return f"Repeats {every} on {day_txt}{until_txt}"
    if freq == "monthly":
        if rule.get("monthly") == "by_weekday":
            nth = int(rule.get("nth") if rule.get("nth") not in (None, "") else 1)
            codes = rule.get("byweekday") or []
            day = WEEKDAY_LABELS[WEEKDAY_CODES.index(codes[0])] if codes and codes[0] in WEEKDAY_CODES else "weekday"
            which = NTH_LABELS.get(nth, "1st")
            return f"Repeats on the {which} {day} of every month{until_txt}"
        return f"Repeats monthly on the same date{until_txt}"
    return "Repeats"


def form_values_from_rule(rule: dict[str, Any] | None) -> dict[str, Any]:
    empty = {
        "repeat_kind": "none",
        "repeat_days": [],
        "repeat_monthly_nth": "1",
        "repeat_monthly_weekday": "MO",
        "repeat_until": "",
    }
    if not rule:
        return empty
    freq = str(rule.get("freq") or "")
    interval = int(rule.get("interval") or 1)
    if freq in {"hourly", "yearly"}:
        kind = freq
    elif freq == "daily":
        kind = "daily"
    elif freq == "weekly":
        kind = "biweekly" if interval == 2 else "weekly"
    elif freq == "monthly":
        kind = "monthly_weekday" if str(rule.get("monthly") or "") == "by_weekday" else "monthly_date"
    else:
        return empty
    days = [str(c).upper() for c in (rule.get("byweekday") or []) if str(c).upper() in WEEKDAY_CODES]
    nth = rule.get("nth")
    return {
        "repeat_kind": kind,
        "repeat_days": days,
        "repeat_monthly_nth": str(int(nth)) if nth not in (None, "") else "1",
        "repeat_monthly_weekday": days[0] if days else "MO",
        "repeat_until": str(rule.get("until") or ""),
    }


def _stamp(start: datetime, d: date) -> datetime:
    return datetime.combine(d, start.time().replace(microsecond=0))


def expand_occurrences(
    starts: datetime,
    rule: dict[str, Any] | None,
    *,
    window_end: datetime | None = None,
) -> list[datetime]:
    if not rule:
        return [starts]
    until = parse_until(rule.get("until"))
    start_d = starts.date()
    hard_end = until
    if window_end:
        win = window_end.date()
        hard_end = min(hard_end, win) if hard_end else win
    if not hard_end:
        hard_end = start_d + timedelta(days=OPEN_DISPLAY_DAYS)
    out: list[datetime] = []
    freq = str(rule.get("freq") or "")
    interval = max(1, int(rule.get("interval") or 1))

    if freq in {"hourly", "yearly"}:
        candidate = starts
        while candidate.date() <= hard_end and len(out) < MAX_OCCURRENCES:
            if window_end and candidate > window_end:
                break
            out.append(candidate)
            candidate = next_occurrence(starts, rule, candidate)
            if candidate is None:
                break
        return out

    if freq == "daily":
        d = start_d
        while d <= hard_end and len(out) < MAX_OCCURRENCES:
            out.append(_stamp(starts, d))
            d += timedelta(days=interval)
        return out or [starts]

    if freq == "weekly":
        wanted = {str(c).upper() for c in (rule.get("byweekday") or []) if str(c).upper() in WEEKDAY_CODES}
        if not wanted:
            wanted = {weekday_code(start_d)}
        week0 = start_d - timedelta(days=start_d.weekday())
        d = start_d
        while d <= hard_end and len(out) < MAX_OCCURRENCES:
            week = d - timedelta(days=d.weekday())
            weeks = (week - week0).days // 7
            if weeks >= 0 and weeks % interval == 0 and weekday_code(d) in wanted:
                out.append(_stamp(starts, d))
            d += timedelta(days=1)
        return out or [starts]

    if freq == "monthly":
        mode = str(rule.get("monthly") or "by_date")
        y, m = start_d.year, start_d.month
        nth = int(rule.get("nth") if rule.get("nth") not in (None, "") else _nth_from_date(start_d))
        codes = [str(c).upper() for c in (rule.get("byweekday") or []) if str(c).upper() in WEEKDAY_CODES]
        wd = WEEKDAY_CODES.index(codes[0]) if codes else start_d.weekday()
        dom = start_d.day
        while len(out) < MAX_OCCURRENCES:
            if mode == "by_weekday":
                occ = _nth_weekday(y, m, wd, nth)
            else:
                last = monthrange(y, m)[1]
                occ = date(y, m, min(dom, last))
            if occ and start_d <= occ <= hard_end:
                out.append(_stamp(starts, occ))
            if occ and occ > hard_end:
                break
            y, m = _add_months(y, m, interval)
            if date(y, m, 1) > hard_end + timedelta(days=32):
                break
        return out or [starts]

    return [starts]


def next_occurrence(starts: datetime, rule: dict[str, Any] | None, after: datetime) -> datetime | None:
    if not rule:
        return None
    until = parse_until(rule.get("until"))
    freq = str(rule.get("freq") or "")
    interval = max(1, int(rule.get("interval") or 1))
    start_d = starts.date()
    clock = starts.time().replace(microsecond=0)

    def ok(dt: datetime) -> bool:
        if dt <= after:
            return False
        if until and dt.date() > until:
            return False
        return True

    if freq in {"hourly", "daily"}:
        step = timedelta(hours=interval) if freq == "hourly" else timedelta(days=interval)
        n = max(0, (after - starts) // step + 1)
        candidate = starts + n * step
        return candidate if ok(candidate) else None

    if freq == "yearly":
        year = max(starts.year, after.year)
        year += (-(year - starts.year)) % interval
        for _ in range(2):
            candidate = datetime.combine(date(year, starts.month,
                min(starts.day, monthrange(year, starts.month)[1])), clock)
            if ok(candidate):
                return candidate
            year += interval
        return None

    if freq == "weekly":
        wanted = {str(c).upper() for c in (rule.get("byweekday") or []) if str(c).upper() in WEEKDAY_CODES}
        if not wanted:
            wanted = {weekday_code(start_d)}
        week0 = start_d - timedelta(days=start_d.weekday())
        d = after.date()
        for _ in range(400):
            d += timedelta(days=1)
            if d < start_d:
                continue
            week = d - timedelta(days=d.weekday())
            weeks = (week - week0).days // 7
            if weeks >= 0 and weeks % interval == 0 and weekday_code(d) in wanted:
                dt = datetime.combine(d, clock)
                return dt if ok(dt) else None
        return None

    if freq == "monthly":
        mode = str(rule.get("monthly") or "by_date")
        nth = int(rule.get("nth") if rule.get("nth") not in (None, "") else _nth_from_date(start_d))
        codes = [str(c).upper() for c in (rule.get("byweekday") or []) if str(c).upper() in WEEKDAY_CODES]
        wd = WEEKDAY_CODES.index(codes[0]) if codes else start_d.weekday()
        dom = start_d.day
        y, m = after.year, after.month
        for _ in range(48):
            if mode == "by_weekday":
                occ = _nth_weekday(y, m, wd, nth)
            else:
                last = monthrange(y, m)[1]
                occ = date(y, m, min(dom, last))
            if occ and occ >= start_d:
                dt = datetime.combine(occ, clock)
                if ok(dt):
                    return dt
            y, m = _add_months(y, m, interval)
        return None

    return None


def display_span(job: ReminderJob, view_end: datetime | None = None) -> tuple[datetime, datetime | None]:
    start = job.series_start or job.send_at
    rule = rule_from_job(job)
    if not rule:
        return start, None
    until = parse_until(rule.get("until"))
    if until:
        end = datetime.combine(until, datetime.max.time().replace(microsecond=0))
        return start, end
    horizon = (view_end or house_now()) + timedelta(days=OPEN_DISPLAY_DAYS)
    return start, horizon


def reminder_occurrences(job: ReminderJob, start: datetime, end: datetime) -> list[datetime]:
    """Kept for tests/tools. Calendar display no longer expands these."""
    if job.status != ReminderStatus.PENDING:
        return []
    rule = rule_from_job(job)
    series = job.series_start or job.send_at
    if not rule:
        if start <= series <= end:
            return [series]
        return []
    return [dt for dt in expand_occurrences(series, rule, window_end=end) if start <= dt <= end]
