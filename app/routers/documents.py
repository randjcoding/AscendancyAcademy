"""Teacher papers: browse folders, preview, and download."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse

from app.database import get_db
from app.dependencies import render, require_teacher, session_token
from app.models import User
from app.security import verify_csrf
from app.services import documents as docs
from app.services.documents import DocumentsError

router = APIRouter()


def _err(rel: str, message: str) -> RedirectResponse:
    return RedirectResponse(
        f"{docs.href(rel)}?error={quote(message)}",
        status_code=303,
    )


@router.get("/documents")
def browse(
    request: Request,
    path: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    try:
        listing = docs.list_dir(path)
    except DocumentsError as exc:
        if exc.status == 404:
            return RedirectResponse("/documents?error=Folder+not+found.", status_code=303)
        return RedirectResponse(f"/documents?error={quote(exc.message)}", status_code=303)
    return render(
        request,
        "documents/browse.html",
        user,
        _db=db,
        listing=listing,
        preview=None,
        error=request.query_params.get("error", ""),
        ok=request.query_params.get("ok", ""),
    )


@router.get("/documents/view")
def view_file(
    request: Request,
    path: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(require_teacher),
):
    try:
        target = docs.resolve_rel(path)
    except DocumentsError as exc:
        return _err("", exc.message)
    if not target.is_file():
        return RedirectResponse(docs.href(path), status_code=303)
    rel = docs.normalize_rel(path)
    parent = "/".join(rel.split("/")[:-1])
    listing = docs.list_dir(parent)
    return render(
        request,
        "documents/browse.html",
        user,
        _db=db,
        listing=listing,
        preview={
            "rel": rel,
            "name": target.name,
            "label": docs.display_label(target.name, is_file=True),
            "kind": docs.viewer_kind(target),
            "kind_label": docs.KIND_LABELS.get(docs.viewer_kind(target), "File"),
            "size_label": docs.human_size(target.stat().st_size),
            "mime": docs.guess_mime(target.name),
            "inline_href": docs.href(rel, "inline"),
            "download_href": docs.href(rel, "download"),
        },
        error=request.query_params.get("error", ""),
        ok=request.query_params.get("ok", ""),
    )


@router.get("/documents/inline")
def inline_file(path: str = "", user: User = Depends(require_teacher)):
    return _file_response(path, inline=True)


@router.get("/documents/download")
def download_file(path: str = "", user: User = Depends(require_teacher)):
    return _file_response(path, inline=False)


def _file_response(path: str, *, inline: bool):
    try:
        target = docs.resolve_rel(path)
    except DocumentsError as exc:
        return RedirectResponse(f"/documents?error={quote(exc.message)}", status_code=303)
    if not target.is_file():
        return RedirectResponse("/documents?error=File+not+found.", status_code=303)
    mime = docs.guess_mime(target.name)
    kind = docs.viewer_kind(target)
    if inline and kind == "html":
        mime = "text/html"
    return FileResponse(
        target,
        media_type=mime,
        filename=target.name,
        content_disposition_type="inline" if inline else "attachment",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.post("/documents/folder")
def make_folder(
    request: Request,
    user: User = Depends(require_teacher),
    csrf_token: str = Form(""),
    parent: str = Form(""),
    name: str = Form(""),
):
    if not verify_csrf(session_token(request), csrf_token):
        return _err(parent, "That form expired. Try again.")
    try:
        rel = docs.create_folder(parent, name)
    except DocumentsError as exc:
        return _err(parent, exc.message)
    return RedirectResponse(f"{docs.href(rel)}?ok=Folder+created.", status_code=303)


@router.post("/documents/upload")
async def upload_files(
    request: Request,
    user: User = Depends(require_teacher),
    csrf_token: str = Form(""),
    parent: str = Form(""),
    files: list[UploadFile] = File(default=[]),
):
    if not verify_csrf(session_token(request), csrf_token):
        return _err(parent, "That form expired. Try again.")
    saved = 0
    last_error = ""
    for item in files:
        if not item.filename:
            continue
        data = await item.read()
        try:
            docs.save_upload(parent, item.filename, data)
            saved += 1
        except DocumentsError as exc:
            last_error = exc.message
    if not saved:
        return _err(parent, last_error or "Choose a file to add.")
    extra = f"?ok={saved}+file{'s' if saved != 1 else ''}+added."
    if last_error:
        extra = f"?ok={saved}+added.&error={quote(last_error)}"
    return RedirectResponse(docs.href(parent) + extra.replace(" ", "+"), status_code=303)


@router.post("/documents/delete")
def remove_entry(
    request: Request,
    user: User = Depends(require_teacher),
    csrf_token: str = Form(""),
    path: str = Form(""),
):
    parent = "/".join(docs.normalize_rel(path).split("/")[:-1]) if path else ""
    if not verify_csrf(session_token(request), csrf_token):
        return _err(parent, "That form expired. Try again.")
    try:
        docs.delete_entry(path)
    except DocumentsError as exc:
        return _err(parent, exc.message)
    return RedirectResponse(f"{docs.href(parent)}?ok=Removed.", status_code=303)
