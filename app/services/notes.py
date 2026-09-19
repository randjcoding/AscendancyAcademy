"""Notebook defaults, page depth, and history snapshots."""
from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, NoteBox, NoteHistory, NotePage, NoteSection, Notebook, ShareScope, User
from app.services import attendance as attendance_svc
from app.services.clock import house_now
from app.services.text import html_to_plain
from app.services.visibility import can_see_notebook, class_ids_for, teacher_course_ids

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
    lifetime: bool = True,
    school_year_id: int | None = None,
) -> Notebook:
    q = select(Notebook).where(Notebook.scope == scope, Notebook.deleted_at.is_(None))
    if scope == ShareScope.PERSONAL:
        q = q.where(Notebook.owner_user_id == owner_user_id)
    elif scope == ShareScope.CLASS:
        q = q.where(Notebook.course_id == course_id)
    else:
        q = q.where(Notebook.course_id.is_(None), Notebook.owner_user_id.is_(None))
    row = db.scalars(q.order_by(Notebook.id)).first()
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
        lifetime=lifetime,
        school_year_id=None if lifetime else school_year_id,
    )
    db.add(row)
    db.flush()
    _section_for(db, row)
    return row


def visible_this_year(notebook: Notebook, year_id: int | None) -> bool:
    if notebook.lifetime or not notebook.school_year_id:
        return True
    return bool(year_id) and notebook.school_year_id == year_id


def ensure_notebooks(db: Session, user: User) -> list[Notebook]:
    year = attendance_svc.current_year(db)
    year_id = year.id if year else None
    personal = _ensure_notebook(
        db,
        name=user.first_name.strip() or user.full_name,
        scope=ShareScope.PERSONAL,
        owner_user_id=user.id,
        course_id=None,
        sort_order=0,
        lifetime=True,
    )
    school = _ensure_notebook(
        db,
        name="School",
        scope=ShareScope.SCHOOL,
        owner_user_id=None,
        course_id=None,
        sort_order=10,
        lifetime=True,
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
                    lifetime=False,
                    school_year_id=course.school_year_id or year_id,
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
    extras = db.scalars(
        select(Notebook).where(
            Notebook.deleted_at.is_(None),
            Notebook.id.notin_([nb.id for nb in out]),
        )
    ).all()
    for nb in extras:
        if can_see_notebook(db, user, nb):
            out.append(nb)
    return [nb for nb in out if visible_this_year(nb, year_id)]


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
    boxes = db.scalars(select(NoteBox).where(NoteBox.page_id == page.id).order_by(NoteBox.z, NoteBox.id)).all()
    html = "\n".join(b.body_html or "" for b in boxes) or (page.body_html or "")
    payload = json.dumps({"boxes": [box_json(b) for b in boxes]})
    db.add(
        NoteHistory(
            page_id=page.id,
            title=page.title,
            body_html=html,
            body_json=payload,
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


def restore_boxes(db: Session, page: NotePage, snap: NoteHistory) -> None:
    for box in db.scalars(select(NoteBox).where(NoteBox.page_id == page.id)).all():
        db.delete(box)
    db.flush()
    rows = []
    try:
        data = json.loads(snap.body_json or "")
        if isinstance(data, dict) and isinstance(data.get("boxes"), list):
            rows = data["boxes"]
    except json.JSONDecodeError:
        rows = []
    if not rows:
        db.add(NoteBox(page_id=page.id, body_html=snap.body_html or "", updated_at=house_now()))
        return
    for row in rows:
        db.add(
            NoteBox(
                page_id=page.id,
                x=max(0, int(row.get("x") or 40)),
                y=max(0, int(row.get("y") or 24)),
                w=max(160, int(row.get("w") or 420)),
                h=max(80, int(row.get("h") or 160)),
                z=int(row.get("z") or 1),
                bg=row.get("bg") or "",
                body_html=row.get("body_html") or "",
                body_json=row.get("body_json") or "",
                revision=0,
                updated_at=house_now(),
            )
        )


def refresh_page_text(db: Session, page: NotePage) -> None:
    boxes = db.scalars(select(NoteBox).where(NoteBox.page_id == page.id).order_by(NoteBox.z, NoteBox.id)).all()
    html = "\n".join(b.body_html or "" for b in boxes) or (page.body_html or "")
    apply_body(page, html, page.body_json)


def ensure_boxes(db: Session, page: NotePage, *, kind: str = "note") -> list[NoteBox]:
    boxes = db.scalars(select(NoteBox).where(NoteBox.page_id == page.id).order_by(NoteBox.z, NoteBox.id)).all()
    if boxes:
        return list(boxes)
    starter = page.body_html or ""
    if kind == "list" and not starter:
        starter = '<ul data-type="taskList"><li data-type="taskItem" data-checked="false"><p></p></li></ul>'
    box = NoteBox(
        page_id=page.id,
        x=40,
        y=24,
        w=720,
        h=200,
        z=1,
        body_html=starter,
        revision=0,
        updated_at=house_now(),
    )
    db.add(box)
    db.flush()
    return [box]


def box_json(box: NoteBox) -> dict:
    return {
        "id": box.id,
        "revision": box.revision,
        "x": box.x,
        "y": box.y,
        "w": box.w,
        "h": box.h,
        "z": box.z,
        "bg": box.bg or "",
        "body_html": box.body_html or "",
        "body_json": box.body_json or "",
    }
