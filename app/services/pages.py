"""Parse page ranges for book assignments."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import Book

_PAGE_CHUNK = re.compile(r"(\d+)\s*(?:-|–|to)\s*(\d+)|(\d+)")
_WORK_WORD = re.compile(r"\b(work|hw|homework|problems?)\b", re.I)
_READ_WORD = re.compile(r"\b(read|reading|no\s*work)\b", re.I)


@dataclass
class PageSpec:
    pages: str
    page_start: int | None
    has_work: bool | None
    extra: str = ""


def normalize_pages(raw: str) -> tuple[str, int | None]:
    text = (raw or "").replace("–", "-").replace("—", "-")
    chunks = []
    first: int | None = None
    for match in _PAGE_CHUNK.finditer(text):
        if match.group(1) and match.group(2):
            start, end = int(match.group(1)), int(match.group(2))
            if end < start:
                start, end = end, start
            chunks.append(f"{start}-{end}")
            first = start if first is None else first
        elif match.group(3):
            num = int(match.group(3))
            chunks.append(str(num))
            first = num if first is None else first
    return (", ".join(chunks), first)


def parse_line(raw: str, default_has_work: bool = True) -> PageSpec | None:
    line = (raw or "").strip()
    if not line:
        return None
    has_work: bool | None = None
    if _READ_WORD.search(line):
        has_work = False
    elif _WORK_WORD.search(line):
        has_work = True
    cleaned = _READ_WORD.sub("", line)
    cleaned = _WORK_WORD.sub("", cleaned)
    pages, start = normalize_pages(cleaned)
    extra = re.sub(r"[\d,\-\s]+", " ", cleaned).strip(" -,").strip()
    if not pages and not extra:
        return None
    return PageSpec(
        pages=pages,
        page_start=start,
        has_work=default_has_work if has_work is None else has_work,
        extra=extra,
    )


def parse_bulk(text: str, default_has_work: bool = True) -> list[PageSpec]:
    out: list[PageSpec] = []
    for line in (text or "").splitlines():
        spec = parse_line(line, default_has_work=default_has_work)
        if spec:
            out.append(spec)
    return out


def assignment_title(book: Book | None, pages: str, extra: str = "", custom: str = "") -> str:
    if (custom or "").strip():
        return custom.strip()
    parts = []
    if book:
        parts.append(book.title)
    if extra:
        parts.append(extra)
    if pages:
        label = f"pp. {pages}" if ("-" in pages or "," in pages) else f"p. {pages}"
        parts.append(label)
    return " ".join(parts) if parts else "Assignment"


def create_page_assignments(
    db,
    *,
    course,
    user_id: int,
    book,
    specs: list[PageSpec],
    category,
    due_date,
    show_on_calendar: bool,
    description: str = "",
) -> int:
    from datetime import datetime

    from app.models import Assignment, AssignmentStatus, CalendarEvent

    count = 0
    for spec in specs:
        title = assignment_title(book, spec.pages, spec.extra)
        assignment = Assignment(
            course_id=course.id,
            category_id=category.id,
            title=title,
            description=description.strip(),
            points_possible=100.0 if spec.has_work else 0.0,
            due_date=due_date,
            show_on_calendar=show_on_calendar,
            book_id=book.id if book else None,
            pages=spec.pages,
            page_start=spec.page_start,
            has_work=bool(spec.has_work),
            status=AssignmentStatus.ASSIGNED,
        )
        db.add(assignment)
        db.flush()
        if show_on_calendar and due_date:
            db.add(
                CalendarEvent(
                    created_by_user_id=user_id,
                    assignment_id=assignment.id,
                    title=f"{course.title}: {assignment.title}",
                    description=assignment.description,
                    starts_at=datetime.combine(due_date, datetime.min.time()),
                    all_day=True,
                )
            )
        count += 1
    return count


def default_category(course, has_work: bool):
    names = {c.name.lower(): c for c in course.categories}
    if has_work:
        for key in ("assignments", "assignment", "other"):
            if key in names:
                return names[key]
    else:
        for key in ("other", "assignments", "assignment"):
            if key in names:
                return names[key]
    return course.categories[0] if course.categories else None
