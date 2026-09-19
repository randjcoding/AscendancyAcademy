"""Notes notebooks, pages, save/409, history, and page-task links."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import NoteBox, NoteHistory, NotePage, NoteSection, Notebook, PageTask, ShareScope, Task
from app.routers.api import _csrf_bad, _err, _must_user
from app.services import attendance as attendance_svc
from app.services.clock import house_now
from app.services.dates import parse_due
from app.services.notes import (
    MAX_PAGE_DEPTH,
    apply_body,
    box_json,
    ensure_boxes,
    ensure_notebooks,
    page_depth,
    refresh_page_text,
    restore_boxes,
    snapshot_page,
)
from app.services.visibility import can_see_notebook, can_see_page, can_see_task, can_write_notebook, can_write_page

router = APIRouter(prefix="/api/notes")

SAFE_FILE = re.compile(r"[^A-Za-z0-9._-]+")


class CsrfBody(BaseModel):
    csrf: str = ""


class NotebookBody(BaseModel):
    csrf: str = ""
    name: str = "Notebook"
    color: str = "#d4b44a"
    scope: str = "personal"
    course_id: int = 0
    lifetime: bool = True


class NotebookPatchBody(BaseModel):
    csrf: str = ""
    name: str = ""
    color: str = ""
    archived: bool | None = None
    scope: str = ""
    course_id: int = 0
    lifetime: bool | None = None


class SectionBody(BaseModel):
    notebook_id: int
    name: str = "Pages"
    color: str = "#2d6a4f"
    csrf: str = ""


class SectionPatchBody(BaseModel):
    csrf: str = ""
    name: str = ""
    color: str = ""


class PageCreateBody(BaseModel):
    notebook_id: int
    section_id: int = 0
    parent_id: int = 0
    title: str = "Untitled"
    kind: str = "note"
    csrf: str = ""


class ShareBody(BaseModel):
    csrf: str = ""
    scope: str = "personal"
    course_id: int = 0


class BoxCreateBody(BaseModel):
    csrf: str = ""
    x: int = 40
    y: int = 24
    w: int = 420
    h: int = 160


class BoxSaveBody(BaseModel):
    csrf: str = ""
    revision: int = 0
    x: int | None = None
    y: int | None = None
    w: int | None = None
    h: int | None = None
    z: int | None = None
    bg: str | None = None
    body_html: str | None = None
    body_json: str | None = None


class PageSaveBody(BaseModel):
    csrf: str = ""
    revision: int = 0
    title: str = ""
    body_html: str = ""
    body_json: str = ""


class ReorderBody(BaseModel):
    csrf: str = ""
    parent_id: int = 0
    section_id: int = 0
    sort_order: int = 0


class MakeTaskBody(BaseModel):
    csrf: str = ""
    title: str
    due: str = ""
    scope: str = ""
    course_id: int = 0


class BringTaskBody(BaseModel):
    csrf: str = ""
    task_id: int


def _page_json(page: NotePage, *, full: bool = False) -> dict:
    data = {
        "id": page.id,
        "notebook_id": page.notebook_id,
        "section_id": page.section_id,
        "parent_id": page.parent_id,
        "title": page.title,
        "kind": page.kind,
        "scope": page.scope,
        "course_id": page.course_id,
        "revision": page.revision,
        "sort_order": page.sort_order,
        "deleted_at": page.deleted_at.isoformat() if page.deleted_at else None,
        "updated_at": page.updated_at.isoformat() if page.updated_at else None,
    }
    if full:
        data["body_html"] = page.body_html or ""
        data["body_json"] = page.body_json or ""
        data["body_plain"] = page.body_plain or ""
    return data


def _get_visible_page(db: Session, user, page_id: int, *, write: bool = False) -> NotePage | JSONResponse:
    page = db.get(NotePage, page_id)
    if not page:
        return _err("That page is gone.", 404)
    ok = can_write_page(db, user, page) if write else can_see_page(db, user, page)
    if not ok:
        return _err("You cannot open that page.", 403)
    return page


@router.get("/tree")
def notes_tree(request: Request, trash: int = 0, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    notebooks = [nb for nb in ensure_notebooks(db, user) if can_see_notebook(db, user, nb)]
    db.commit()
    want_trash = bool(trash)
    notebooks = [nb for nb in notebooks if want_trash or not getattr(nb, "archived", False)]
    out = []
    for nb in notebooks:
        sections = [
            s
            for s in db.scalars(
                select(NoteSection)
                .where(NoteSection.notebook_id == nb.id, NoteSection.deleted_at.is_(None))
                .order_by(NoteSection.sort_order, NoteSection.id)
            ).all()
        ]
        pages = db.scalars(
            select(NotePage)
            .where(NotePage.notebook_id == nb.id)
            .order_by(NotePage.sort_order, NotePage.id)
        ).all()
        extras = []
        if nb.scope == ShareScope.SCHOOL:
            extras = db.scalars(
                select(NotePage).where(
                    NotePage.scope == ShareScope.SCHOOL,
                    NotePage.notebook_id != nb.id,
                    NotePage.deleted_at.is_(None),
                )
            ).all()
        elif nb.scope == ShareScope.CLASS and nb.course_id:
            extras = db.scalars(
                select(NotePage).where(
                    NotePage.scope == ShareScope.CLASS,
                    NotePage.course_id == nb.course_id,
                    NotePage.notebook_id != nb.id,
                    NotePage.deleted_at.is_(None),
                )
            ).all()
        pages = [p for p in list(pages) + list(extras) if can_see_page(db, user, p)]
        if want_trash:
            pages = [p for p in pages if p.deleted_at]
        else:
            pages = [p for p in pages if not p.deleted_at]
        out.append(
            {
                "id": nb.id,
                "name": nb.name,
                "color": nb.color or "#d4b44a",
                "scope": nb.scope,
                "course_id": nb.course_id,
                "archived": bool(getattr(nb, "archived", False)),
                "lifetime": bool(getattr(nb, "lifetime", False)),
                "school_year_id": nb.school_year_id,
                "can_write": can_write_notebook(db, user, nb),
                "sections": [
                    {"id": s.id, "name": s.name, "color": getattr(s, "color", None) or "#2d6a4f", "sort_order": s.sort_order}
                    for s in sections
                ],
                "pages": [_page_json(p) for p in pages],
            }
        )
    return {"notebooks": out, "can_write_school": user.is_teacher}


@router.get("/search")
def notes_search(request: Request, q: str = "", db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    needle = (q or "").strip()
    if len(needle) < 2:
        return {"pages": []}
    like = f"%{needle}%"
    rows = db.scalars(
        select(NotePage).where(
            NotePage.deleted_at.is_(None),
            or_(NotePage.title.ilike(like), NotePage.body_plain.ilike(like)),
        )
    ).all()
    hits = [p for p in rows if can_see_page(db, user, p)][:40]
    return {
        "pages": [
            {
                **_page_json(p),
                "snippet": (p.body_plain or "")[:160],
            }
            for p in hits
        ]
    }


@router.post("/sections")
def create_section(body: SectionBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    notebook = db.get(Notebook, body.notebook_id)
    if not notebook or not can_write_notebook(db, user, notebook):
        return _err("You cannot add a section there.", 403)
    name = body.name.strip() or "Pages"
    section = NoteSection(notebook_id=notebook.id, name=name, color=body.color or "#2d6a4f")
    db.add(section)
    db.commit()
    db.refresh(section)
    return {"ok": True, "section": {"id": section.id, "name": section.name, "color": section.color}}


@router.post("/pages")
def create_page(body: PageCreateBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    notebook = db.get(Notebook, body.notebook_id)
    if not notebook or not can_write_notebook(db, user, notebook):
        return _err("You cannot add a page there.", 403)
    section_id = body.section_id or None
    parent_id = body.parent_id or None
    parent = db.get(NotePage, parent_id) if parent_id else None
    if parent:
        if parent.notebook_id != notebook.id or not can_write_page(db, user, parent):
            return _err("You cannot add a page there.", 403)
        if page_depth(db, parent) >= MAX_PAGE_DEPTH:
            return _err("That nest is already five deep.")
        section_id = parent.section_id
    owner_id = notebook.owner_user_id or user.id
    page = NotePage(
        notebook_id=notebook.id,
        section_id=section_id,
        parent_id=parent.id if parent else None,
        owner_user_id=owner_id if notebook.scope == ShareScope.PERSONAL else user.id,
        scope=notebook.scope,
        course_id=notebook.course_id,
        title=body.title.strip() or "Untitled",
        kind="list" if body.kind == "list" else "note",
        updated_at=house_now(),
    )
    db.add(page)
    db.flush()
    ensure_boxes(db, page, kind=page.kind)
    db.commit()
    db.refresh(page)
    return {"ok": True, "page": _page_json(page, full=True)}


@router.get("/pages/{page_id}")
def get_page(page_id: int, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    page = _get_visible_page(db, user, page_id)
    if isinstance(page, JSONResponse):
        return page
    links = db.scalars(select(PageTask).where(PageTask.page_id == page.id)).all()
    tasks = []
    for link in links:
        task = db.get(Task, link.task_id)
        if task and can_see_task(db, user, task):
            tasks.append(
                {
                    "id": task.id,
                    "title": task.title,
                    "completed": task.completed,
                    "due": task.due_at.date().isoformat() if task.due_at else "",
                }
            )
    boxes = ensure_boxes(db, page, kind=page.kind)
    db.commit()
    return {
        "page": _page_json(page, full=True),
        "boxes": [box_json(b) for b in boxes],
        "can_write": can_write_page(db, user, page),
        "tasks": tasks,
    }


@router.post("/pages/{page_id}/save")
def save_page(page_id: int, body: PageSaveBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    page = _get_visible_page(db, user, page_id, write=True)
    if isinstance(page, JSONResponse):
        return page
    if body.revision != page.revision:
        return JSONResponse({"error": "conflict", "revision": page.revision}, status_code=409)
    snapshot_page(db, page)
    if body.title.strip():
        page.title = body.title.strip()[:255]
    apply_body(page, body.body_html, body.body_json)
    page.revision += 1
    db.add(page)
    db.commit()
    db.refresh(page)
    return {"ok": True, "revision": page.revision, "title": page.title, "saved_at": house_now().strftime("%H:%M:%S")}


@router.post("/pages/{page_id}/delete")
def delete_page(page_id: int, body: CsrfBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    page = _get_visible_page(db, user, page_id, write=True)
    if isinstance(page, JSONResponse):
        return page
    page.deleted_at = house_now()
    db.commit()
    return {"ok": True}


@router.post("/pages/{page_id}/restore")
def restore_page(page_id: int, body: CsrfBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    page = db.get(NotePage, page_id)
    if not page or not can_write_page(db, user, page):
        return _err("You cannot restore that page.", 403)
    page.deleted_at = None
    db.commit()
    return {"ok": True}


@router.post("/pages/{page_id}/reorder")
def reorder_page(page_id: int, body: ReorderBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    page = _get_visible_page(db, user, page_id, write=True)
    if isinstance(page, JSONResponse):
        return page
    parent = db.get(NotePage, body.parent_id) if body.parent_id else None
    if parent:
        if parent.notebook_id != page.notebook_id:
            return _err("Keep pages in the same notebook.")
        if page_depth(db, parent) >= MAX_PAGE_DEPTH:
            return _err("That nest is already five deep.")
        page.parent_id = parent.id
        page.section_id = parent.section_id
    else:
        page.parent_id = None
        if body.section_id:
            page.section_id = body.section_id
    page.sort_order = body.sort_order
    db.commit()
    return {"ok": True}


@router.get("/pages/{page_id}/history")
def page_history(page_id: int, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    page = _get_visible_page(db, user, page_id)
    if isinstance(page, JSONResponse):
        return page
    rows = db.scalars(
        select(NoteHistory).where(NoteHistory.page_id == page.id).order_by(NoteHistory.id.desc())
    ).all()
    return {
        "history": [
            {
                "id": h.id,
                "title": h.title,
                "created_at": h.created_at.isoformat() if h.created_at else "",
                "preview": (h.body_html or "")[:200],
            }
            for h in rows
        ],
        "can_write": can_write_page(db, user, page),
    }


@router.post("/pages/{page_id}/history/{history_id}/restore")
def restore_history(page_id: int, history_id: int, body: CsrfBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    page = _get_visible_page(db, user, page_id, write=True)
    if isinstance(page, JSONResponse):
        return page
    snap = db.get(NoteHistory, history_id)
    if not snap or snap.page_id != page.id:
        return _err("That snapshot is gone.", 404)
    snapshot_page(db, page)
    page.title = snap.title or page.title
    restore_boxes(db, page, snap)
    refresh_page_text(db, page)
    page.revision += 1
    db.commit()
    db.refresh(page)
    return {"ok": True, "page": _page_json(page, full=True), "revision": page.revision}


@router.post("/pages/{page_id}/make-task")
def make_task(page_id: int, body: MakeTaskBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    page = _get_visible_page(db, user, page_id)
    if isinstance(page, JSONResponse):
        return page
    title = body.title.strip()
    if not title:
        return _err("Type a task.")
    scope = (body.scope or page.scope or ShareScope.PERSONAL).strip().lower()
    if scope not in ShareScope.ALL:
        scope = ShareScope.PERSONAL
    if not user.is_teacher:
        scope = ShareScope.PERSONAL
    due_at = parse_due(body.due) if body.due.strip() else None
    task = Task(
        created_by_user_id=user.id,
        owner_user_id=user.id if scope == ShareScope.PERSONAL else page.owner_user_id,
        title=title,
        scope=scope,
        course_id=body.course_id or page.course_id,
        due_at=due_at,
        show_on_calendar=True,
    )
    db.add(task)
    db.flush()
    if not db.scalar(select(PageTask).where(PageTask.page_id == page.id, PageTask.task_id == task.id)):
        db.add(PageTask(page_id=page.id, task_id=task.id))
    db.commit()
    return {"ok": True, "task": {"id": task.id, "title": task.title}}


@router.post("/pages/{page_id}/bring-in-task")
def bring_in_task(page_id: int, body: BringTaskBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    page = _get_visible_page(db, user, page_id)
    if isinstance(page, JSONResponse):
        return page
    task = db.get(Task, body.task_id)
    if not task or not can_see_task(db, user, task):
        return _err("That to-do is not yours to bring in.", 403)
    existing = db.scalar(select(PageTask).where(PageTask.page_id == page.id, PageTask.task_id == task.id))
    if not existing:
        db.add(PageTask(page_id=page.id, task_id=task.id))
        db.commit()
    return {"ok": True, "task": {"id": task.id, "title": task.title, "completed": task.completed}}


@router.post("/pages/{page_id}/unlink-task/{task_id}")
def unlink_task(page_id: int, task_id: int, body: CsrfBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    page = _get_visible_page(db, user, page_id)
    if isinstance(page, JSONResponse):
        return page
    link = db.scalar(select(PageTask).where(PageTask.page_id == page.id, PageTask.task_id == task_id))
    if link:
        db.delete(link)
        db.commit()
    return {"ok": True}


@router.post("/pages/{page_id}/upload")
async def upload_note_image(
    page_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    page = _get_visible_page(db, user, page_id, write=True)
    if isinstance(page, JSONResponse):
        return page
    raw = await file.read()
    if not raw or len(raw) > 8_000_000:
        return _err("That picture is too big.")
    ext = Path(file.filename or "pic.png").suffix.lower() or ".png"
    if ext not in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        ext = ".png"
    folder = settings.storage_path / "notes" / str(page.id)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{int(house_now().timestamp())}-{SAFE_FILE.sub('', Path(file.filename or 'pic').stem)[:40]}{ext}"
    (folder / name).write_bytes(raw)
    return {"ok": True, "url": f"/api/notes/files/{page.id}/{name}"}


@router.get("/files/{page_id}/{name}")
def note_file(page_id: int, name: str, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    page = _get_visible_page(db, user, page_id)
    if isinstance(page, JSONResponse):
        return page
    safe = Path(name).name
    path = settings.storage_path / "notes" / str(page.id) / safe
    if not path.is_file():
        return _err("That picture is gone.", 404)
    return FileResponse(path)


@router.post("/notebooks")
def create_notebook(body: NotebookBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    scope = (body.scope or ShareScope.PERSONAL).strip().lower()
    if scope not in ShareScope.ALL:
        scope = ShareScope.PERSONAL
    if not user.is_teacher:
        scope = ShareScope.PERSONAL
    year = attendance_svc.current_year(db)
    keep = bool(body.lifetime)
    nb = Notebook(
        name=body.name.strip() or "Notebook",
        color=body.color or "#d4b44a",
        scope=scope,
        owner_user_id=user.id if scope == ShareScope.PERSONAL else None,
        course_id=body.course_id or None,
        lifetime=keep,
        school_year_id=None if keep else (year.id if year else None),
    )
    db.add(nb)
    db.flush()
    db.add(NoteSection(notebook_id=nb.id, name="Pages", color="#2d6a4f"))
    db.commit()
    db.refresh(nb)
    return {
        "ok": True,
        "notebook": {
            "id": nb.id,
            "name": nb.name,
            "color": nb.color,
            "scope": nb.scope,
            "lifetime": nb.lifetime,
        },
    }


@router.post("/notebooks/{notebook_id}")
def patch_notebook(notebook_id: int, body: NotebookPatchBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    nb = db.get(Notebook, notebook_id)
    if not nb or not can_write_notebook(db, user, nb):
        return _err("You cannot change that notebook.", 403)
    if body.name.strip():
        nb.name = body.name.strip()[:160]
    if body.color.strip():
        nb.color = body.color.strip()[:16]
    if body.archived is not None:
        nb.archived = body.archived
    if body.lifetime is not None:
        nb.lifetime = bool(body.lifetime)
        if nb.lifetime:
            nb.school_year_id = None
        elif not nb.school_year_id:
            year = attendance_svc.current_year(db)
            nb.school_year_id = year.id if year else None
    if body.scope.strip() and user.is_teacher:
        scope = body.scope.strip().lower()
        if scope in ShareScope.ALL:
            nb.scope = scope
            nb.course_id = body.course_id or None
            for page in db.scalars(select(NotePage).where(NotePage.notebook_id == nb.id)).all():
                page.scope = scope
                page.course_id = nb.course_id
    db.commit()
    return {"ok": True}


@router.post("/notebooks/{notebook_id}/delete")
def delete_notebook(notebook_id: int, body: CsrfBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    nb = db.get(Notebook, notebook_id)
    if not nb or not can_write_notebook(db, user, nb):
        return _err("You cannot remove that notebook.", 403)
    nb.deleted_at = house_now()
    db.commit()
    return {"ok": True}


@router.post("/sections/{section_id}")
def patch_section(section_id: int, body: SectionPatchBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    section = db.get(NoteSection, section_id)
    notebook = db.get(Notebook, section.notebook_id) if section else None
    if not section or not notebook or not can_write_notebook(db, user, notebook):
        return _err("You cannot change that section.", 403)
    if body.name.strip():
        section.name = body.name.strip()[:160]
    if body.color.strip():
        section.color = body.color.strip()[:16]
    db.commit()
    return {"ok": True}


@router.post("/sections/{section_id}/delete")
def delete_section(section_id: int, body: CsrfBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    section = db.get(NoteSection, section_id)
    notebook = db.get(Notebook, section.notebook_id) if section else None
    if not section or not notebook or not can_write_notebook(db, user, notebook):
        return _err("You cannot remove that section.", 403)
    others = db.scalars(
        select(NoteSection).where(NoteSection.notebook_id == notebook.id, NoteSection.deleted_at.is_(None))
    ).all()
    if len(others) <= 1:
        return _err("Keep at least one section.")
    section.deleted_at = house_now()
    for page in db.scalars(select(NotePage).where(NotePage.section_id == section.id)).all():
        page.deleted_at = house_now()
    db.commit()
    return {"ok": True}


@router.post("/pages/{page_id}/share")
def share_page(page_id: int, body: ShareBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    page = _get_visible_page(db, user, page_id, write=True)
    if isinstance(page, JSONResponse):
        return page
    if not user.is_teacher:
        return _err("Only teachers can share a page.", 403)
    scope = (body.scope or ShareScope.PERSONAL).strip().lower()
    if scope not in ShareScope.ALL:
        return _err("Pick who can see this.")
    page.scope = scope
    page.course_id = body.course_id or None
    db.commit()
    return {"ok": True, "scope": page.scope, "course_id": page.course_id}


@router.post("/pages/{page_id}/boxes")
def create_box(page_id: int, body: BoxCreateBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    page = _get_visible_page(db, user, page_id, write=True)
    if isinstance(page, JSONResponse):
        return page
    top = db.scalar(select(NoteBox.z).where(NoteBox.page_id == page.id).order_by(NoteBox.z.desc())) or 0
    box = NoteBox(
        page_id=page.id,
        x=max(0, body.x),
        y=max(0, body.y),
        w=max(160, body.w),
        h=max(80, body.h),
        z=top + 1,
        updated_at=house_now(),
    )
    db.add(box)
    snapshot_page(db, page)
    db.commit()
    db.refresh(box)
    return {"ok": True, "box": box_json(box)}


@router.post("/boxes/{box_id}")
def save_box(box_id: int, body: BoxSaveBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    box = db.get(NoteBox, box_id)
    if not box:
        return _err("That box is gone.", 404)
    page = _get_visible_page(db, user, box.page_id, write=True)
    if isinstance(page, JSONResponse):
        return page
    if body.revision != box.revision:
        return JSONResponse({"error": "conflict", "revision": box.revision}, status_code=409)
    snapshot_page(db, page)
    if body.x is not None:
        box.x = max(0, body.x)
    if body.y is not None:
        box.y = max(0, body.y)
    if body.w is not None:
        box.w = max(160, body.w)
    if body.h is not None:
        box.h = max(80, body.h)
    if body.z is not None:
        box.z = body.z
    if body.bg is not None:
        box.bg = body.bg
    if body.body_html is not None:
        box.body_html = body.body_html
    if body.body_json is not None:
        box.body_json = body.body_json
    box.revision += 1
    box.updated_at = house_now()
    refresh_page_text(db, page)
    db.commit()
    db.refresh(box)
    return {"ok": True, "box": box_json(box), "revision": box.revision}


@router.post("/boxes/{box_id}/delete")
def delete_box(box_id: int, body: CsrfBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    box = db.get(NoteBox, box_id)
    if not box:
        return _err("That box is gone.", 404)
    page = _get_visible_page(db, user, box.page_id, write=True)
    if isinstance(page, JSONResponse):
        return page
    snapshot_page(db, page)
    db.delete(box)
    db.flush()
    refresh_page_text(db, page)
    db.commit()
    return {"ok": True}


@router.post("/pages/{page_id}/recover-draft")
def recover_draft(page_id: int, body: PageSaveBody, request: Request, db: Session = Depends(get_db)):
    user = _must_user(request, db)
    if isinstance(user, JSONResponse):
        return user
    if _csrf_bad(request, body.csrf):
        return _err("That form expired.", 403)
    page = _get_visible_page(db, user, page_id)
    if isinstance(page, JSONResponse):
        return page
    if not can_write_page(db, user, page):
        return _err("You cannot recover that draft.", 403)
    recovered = NotePage(
        notebook_id=page.notebook_id,
        section_id=page.section_id,
        parent_id=page.parent_id,
        owner_user_id=page.owner_user_id,
        scope=page.scope,
        course_id=page.course_id,
        title=(body.title.strip() or page.title) + " (local recovery)",
        kind=page.kind,
        updated_at=house_now(),
    )
    db.add(recovered)
    db.flush()
    box = NoteBox(page_id=recovered.id, body_html=body.body_html or "", body_json=body.body_json or "", updated_at=house_now())
    db.add(box)
    refresh_page_text(db, recovered)
    db.commit()
    db.refresh(recovered)
    return {"ok": True, "page": _page_json(recovered, full=True)}
