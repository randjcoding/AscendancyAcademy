"""Attendance totals and month grids."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AttendanceDay, AttendanceStatus, SchoolYear, Student

CYCLE = [
    AttendanceStatus.PRESENT,
    AttendanceStatus.ABSENT,
    AttendanceStatus.EXCUSED,
    AttendanceStatus.OFF,
]


@dataclass
class AttendanceTotals:
    present: int
    absent: int
    excused: int
    off: int
    school_days: int
    remaining: int
    target: int


def current_year(db: Session, on: date | None = None) -> SchoolYear | None:
    day = on or date.today()
    year = db.scalar(select(SchoolYear).where(SchoolYear.is_current.is_(True)))
    if year and year.start_date <= day <= year.end_date:
        return year
    return db.scalar(
        select(SchoolYear).where(SchoolYear.start_date <= day, SchoolYear.end_date >= day)
    ) or year


def day_record(db: Session, student_id: int, on: date) -> AttendanceDay | None:
    return db.scalar(
        select(AttendanceDay).where(
            AttendanceDay.student_id == student_id, AttendanceDay.on_date == on
        )
    )


def implied_status(on: date, record: AttendanceDay | None) -> AttendanceStatus | None:
    if record:
        return record.status
    if on.weekday() >= 5:
        return AttendanceStatus.OFF
    return None


def next_status(current: AttendanceStatus | None) -> AttendanceStatus:
    if current is None:
        return AttendanceStatus.PRESENT
    try:
        idx = CYCLE.index(current)
    except ValueError:
        return AttendanceStatus.PRESENT
    return CYCLE[(idx + 1) % len(CYCLE)]


def totals(db: Session, student: Student, year: SchoolYear) -> AttendanceTotals:
    rows = db.scalars(
        select(AttendanceDay).where(
            AttendanceDay.student_id == student.id,
            AttendanceDay.school_year_id == year.id,
        )
    ).all()
    present = sum(1 for r in rows if r.status == AttendanceStatus.PRESENT)
    absent = sum(1 for r in rows if r.status == AttendanceStatus.ABSENT)
    excused = sum(1 for r in rows if r.status == AttendanceStatus.EXCUSED)
    off = sum(1 for r in rows if r.status == AttendanceStatus.OFF)
    school_days = present + absent + excused
    remaining = max(0, year.instructional_day_target - present)
    return AttendanceTotals(
        present=present,
        absent=absent,
        excused=excused,
        off=off,
        school_days=school_days,
        remaining=remaining,
        target=year.instructional_day_target,
    )


def week_strip(db: Session, student_id: int, around: date | None = None) -> list[dict]:
    today = around or date.today()
    start = today - timedelta(days=today.weekday())
    out = []
    for i in range(7):
        day = start + timedelta(days=i)
        record = day_record(db, student_id, day)
        out.append(
            {
                "date": day,
                "status": implied_status(day, record),
                "recorded": record is not None,
                "is_today": day == today,
            }
        )
    return out


def month_cells(db: Session, student_id: int, year: int, month: int) -> list[dict]:
    weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(year, month)
    cells = []
    for week in weeks:
        row = []
        for day in week:
            record = day_record(db, student_id, day)
            row.append(
                {
                    "date": day,
                    "in_month": day.month == month,
                    "status": implied_status(day, record) if day.month == month else None,
                    "recorded": record is not None and day.month == month,
                    "is_today": day == date.today(),
                }
            )
        cells.append(row)
    return cells


def year_months(year: SchoolYear) -> list[tuple[int, int]]:
    months = []
    cursor = date(year.start_date.year, year.start_date.month, 1)
    last = date(year.end_date.year, year.end_date.month, 1)
    while cursor <= last:
        months.append((cursor.year, cursor.month))
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return months


def ocr_code(student: Student, year: int, month: int) -> str:
    slug = (student.preferred_name or student.user.first_name or "STUDENT").upper()
    slug = "".join(ch for ch in slug if ch.isalnum())[:12] or "STUDENT"
    return f"AA|{slug}|{year:04d}-{month:02d}"
