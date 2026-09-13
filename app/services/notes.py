"""Notebook defaults, page depth, and history snapshots."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, NoteHistory, NotePage, NoteSection, Notebook, ShareScope, User
from app.services.clock import house_now
from app.services.text import html_to_plain
from app.services.visibility import class_ids_for, teacher_course_ids

MAX_PAGE_DEPTH = 5
HISTORY_KEEP = 100


def _section_for(db: Session, notebook: Notebook) -> NoteSection:
    section = db.scalar(
        select(NoteSection)
        .where(NoteSection.notebook_id == notebook.id, NoteSection.deleted_at.is_(None))
        .order_by(NoteSection.sort_order, NoteSection.id)
    )
    if section:
        return section
    section = NoteSection(notebook_id=notebook.id, name="Pages", sort_order=0)
    db.add(section)
    db.flush()
    return section


def _ensure_notebook(
    db: Session,
    *,
    name: str,
    scope: str,
    owner_user_id: int | None,
    course_id: int | None,
    sort_order: int,
) -> Notebook:
    q = select(Notebook).where(Notebook.scope == scope, Notebook.deleted_at.is_(None))
    if scope == ShareScope.PERSONAL:
        q = q.where(Notebook.owner_user_id == owner_user_id)
    elif scope == ShareScope.CLASS:
        q = q.where(Notebook.course_id == course_id)
    else:
        q = q.where(Notebook.course_id.is_(None), Notebook.owner_user_id.is_(None))
    row = db.scalar(q)
    if row:
        if row.name != name:
            row.name = name
            db.add(row)
        return row
    row = Notebook(
        name=name,
        scope=scope,
        owner_user_id=owner_user_id,
        course_id=course_id,
        sort_order=sort_order,
    )
    db.add(row)
    db.flush()
    _section_for(db, row)
    return row


def ensure_notebooks(db: Session, user: User) -> list[Notebook]:
    personal = _ensure_notebook(
        db,
        name=user.first_name.strip() or user.full_name,
        scope=ShareScope.PERSONAL,
        owner_user_id=user.id,
        course_id=None,
        sort_order=0,
    )
    school = _ensure_notebook(
        db,
        name="School",
        scope=ShareScope.SCHOOL,
        owner_user_id=None,
        course_id=None,
        sort_order=10,
    )
    out = [personal, school]
    if user.is_teacher:
        for course_id in sorted(teacher_course_ids(db, user)):
            course = db.get(Course, course_id)
            if not course:
                continue
            out.append(
                _ensure_notebook(
                    db,
                    name=course.title,
                    scope=ShareScope.CLASS,
                    owner_user_id=None,
                    course_id=course.id,
                    sort_order=20 + course.id,
                )
            )
    else:
        for course_id in sorted(class_ids_for(db, user)):
            course = db.get(Course, course_id)
            if not course:
                continue
            existing = db.scalar(
                select(Notebook).where(
                    Notebook.scope == ShareScope.CLASS,
                    Notebook.course_id == course.id,
                    Notebook.deleted_at.is_(None),
                )
            )
            if existing:
                out.append(existing)
    db.flush()
    return out


def page_depth(db: Session, page: NotePage) -> int:
    depth = 1
    seen: set[int] = set()
    cur = page
    while cur.parent_id and cur.parent_id not in seen:
        seen.add(cur.id)
        parent = db.get(NotePage, cur.parent_id)
        if not parent:
            break
        depth += 1
        cur = parent
    return depth


def snapshot_page(db: Session, page: NotePage) -> None:
    db.add(
        NoteHistory(
            page_id=page.id,
            title=page.title,
            body_html=page.body_html or "",
            body_json=page.body_json or "",
            created_at=house_now(),
        )
    )
    db.flush()
    extras = db.scalars(
        select(NoteHistory)
        .where(NoteHistory.page_id == page.id)
        .order_by(NoteHistory.id.desc())
        .offset(HISTORY_KEEP)
    ).all()
    for row in extras:
        db.delete(row)


def apply_body(page: NotePage, html: str, json_text: str = "") -> None:
    page.body_html = html or ""
    page.body_json = json_text or ""
    page.body_plain = html_to_plain(page.body_html)
    page.updated_at = house_now()
