"""Teacher document library on disk under Documents/."""
from __future__ import annotations

import mimetypes
import re
import shutil
from pathlib import Path
from urllib.parse import quote

from app.config import BASE_DIR

ROOT_NAME = "Documents"
IMPORTANT_FOLDER = "Home School Important Documents"
PHOTOS_FOLDER = "Teacher photos"
OLD_NOI_FOLDER = "NOI Approval"
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
SKIP_NAMES = frozenset({".gitkeep", "Thumbs.db", ".DS_Store"})

ALLOWED_EXT = frozenset(
    {
        ".pdf",
        ".doc",
        ".docx",
        ".odt",
        ".rtf",
        ".xls",
        ".xlsx",
        ".ods",
        ".csv",
        ".ppt",
        ".pptx",
        ".odp",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".bmp",
        ".tif",
        ".tiff",
        ".svg",
        ".txt",
        ".md",
        ".json",
        ".html",
        ".htm",
        ".zip",
    }
)

KIND_LABELS = {
    "folder": "Folder",
    "pdf": "PDF",
    "docx": "Word",
    "xlsx": "Spreadsheet",
    "pptx": "Slides",
    "image": "Picture",
    "text": "Text",
    "html": "Web page",
    "download": "File",
}


class DocumentsError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def library_root() -> Path:
    root = (BASE_DIR / ROOT_NAME).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def ensure_library_layout() -> None:
    root = library_root()
    important = root / IMPORTANT_FOLDER
    important.mkdir(exist_ok=True)
    (root / PHOTOS_FOLDER).mkdir(exist_ok=True)
    old_noi = root / OLD_NOI_FOLDER
    new_noi = important / OLD_NOI_FOLDER
    if old_noi.is_dir() and not new_noi.exists():
        shutil.move(str(old_noi), str(new_noi))
    elif old_noi.is_dir() and new_noi.exists():
        for child in old_noi.iterdir():
            dest = new_noi / child.name
            if not dest.exists():
                shutil.move(str(child), str(dest))
        shutil.rmtree(old_noi, ignore_errors=True)


def all_folders() -> list[dict]:
    ensure_library_layout()
    root = library_root()
    rows = [{"rel": "", "label": "Documents", "depth": 0}]
    for path in sorted(root.rglob("*"), key=lambda p: str(p).lower()):
        if not path.is_dir():
            continue
        if any(part.startswith(".") or part in SKIP_NAMES for part in path.relative_to(root).parts):
            continue
        rel = normalize_rel(str(path.relative_to(root)).replace("\\", "/"))
        parts = rel.split("/") if rel else []
        rows.append(
            {
                "rel": rel,
                "label": " / ".join(display_label(p) for p in parts),
                "depth": len(parts),
            }
        )
    return rows


def normalize_rel(rel: str | None) -> str:
    rel = (rel or "").replace("\\", "/").strip("/")
    if not rel:
        return ""
    parts = [p for p in rel.split("/") if p and p != "."]
    if any(p == ".." for p in parts):
        raise DocumentsError("That path is not allowed.", 404)
    return "/".join(parts)


def resolve_rel(rel: str | None) -> Path:
    root = library_root()
    norm = normalize_rel(rel)
    target = (root / norm).resolve() if norm else root
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise DocumentsError("That path is not allowed.", 403) from exc
    return target


def encode_path(rel: str) -> str:
    return quote(normalize_rel(rel), safe="/")


def href(rel: str, action: str = "") -> str:
    q = encode_path(rel)
    if action:
        return f"/documents/{action}?path={q}"
    if q:
        return f"/documents?path={q}"
    return "/documents"


def viewer_kind(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext == ".docx":
        return "docx"
    if ext in {".xlsx", ".xls", ".ods", ".csv"}:
        return "xlsx"
    if ext in {".pptx", ".ppt", ".odp"}:
        return "pptx"
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"}:
        return "image"
    if ext in {".html", ".htm"}:
        return "html"
    if ext in {".txt", ".md", ".json", ".rtf"}:
        return "text"
    return "download"


def guess_mime(name: str) -> str:
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


def display_label(name: str, *, is_file: bool = False) -> str:
    base = Path(name).stem if is_file else name
    label = re.sub(r"\s+", " ", base).strip(" -–_")
    return label or name


def human_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


def kind_badge(kind: str) -> str:
    return {
        "folder": "DIR",
        "pdf": "PDF",
        "docx": "DOC",
        "xlsx": "XLS",
        "pptx": "PPT",
        "image": "IMG",
        "text": "TXT",
        "html": "WEB",
        "download": "FILE",
    }.get(kind, "FILE")


def _safe_name(name: str) -> str:
    name = (name or "").strip().replace("\\", "/").split("/")[-1]
    name = re.sub(r"\s+", " ", name).strip()
    if not name or name in {".", ".."} or name.startswith("."):
        raise DocumentsError("That name is not allowed.")
    if name in SKIP_NAMES:
        raise DocumentsError("That name is reserved.")
    return name


def list_dir(rel: str | None = "") -> dict:
    ensure_library_layout()
    norm = normalize_rel(rel)
    target = resolve_rel(norm)
    if not target.exists():
        raise DocumentsError("Folder not found.", 404)
    if not target.is_dir():
        raise DocumentsError("That is a file, not a folder.", 400)

    folders: list[dict] = []
    files: list[dict] = []
    for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if child.name.startswith(".") or child.name in SKIP_NAMES:
            continue
        child_rel = f"{norm}/{child.name}".strip("/") if norm else child.name
        if child.is_dir():
            folders.append(
                {
                    "name": child.name,
                    "label": display_label(child.name),
                    "rel": child_rel,
                    "kind": "folder",
                    "badge": "DIR",
                    "href": href(child_rel),
                }
            )
        elif child.is_file():
            kind = viewer_kind(child)
            files.append(
                {
                    "name": child.name,
                    "label": display_label(child.name, is_file=True),
                    "rel": child_rel,
                    "kind": kind,
                    "kind_label": KIND_LABELS.get(kind, "File"),
                    "badge": kind_badge(kind),
                    "size": child.stat().st_size,
                    "size_label": human_size(child.stat().st_size),
                    "mime": guess_mime(child.name),
                    "view_href": href(child_rel, "view"),
                    "inline_href": href(child_rel, "inline"),
                    "download_href": href(child_rel, "download"),
                }
            )

    crumbs = [{"label": "Documents", "href": "/documents" if norm else ""}]
    acc: list[str] = []
    parts = norm.split("/") if norm else []
    for i, part in enumerate(parts):
        acc.append(part)
        part_rel = "/".join(acc)
        crumbs.append(
            {
                "label": display_label(part),
                "href": href(part_rel) if i < len(parts) - 1 else "",
            }
        )
    parent = "/".join(parts[:-1]) if parts else ""
    return {
        "rel": norm,
        "title": display_label(parts[-1]) if parts else "Documents",
        "destinations": all_folders(),
        "folders": folders,
        "files": files,
        "crumbs": crumbs,
        "parent_href": href(parent) if norm else "",
        "folder_count": len(folders),
        "file_count": len(files),
    }


def create_folder(parent_rel: str | None, name: str) -> str:
    parent = resolve_rel(parent_rel)
    if not parent.is_dir():
        raise DocumentsError("Folder not found.", 404)
    folder = parent / _safe_name(name)
    if folder.exists():
        raise DocumentsError("A folder with that name is already there.")
    folder.mkdir()
    rel = normalize_rel(parent_rel)
    return f"{rel}/{folder.name}".strip("/")


def save_upload(parent_rel: str | None, filename: str, data: bytes) -> str:
    if len(data) > MAX_UPLOAD_BYTES:
        raise DocumentsError("That file is too big (50 MB limit).")
    name = _safe_name(filename)
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise DocumentsError("That file type is not allowed.")
    parent = resolve_rel(parent_rel)
    if not parent.is_dir():
        raise DocumentsError("Folder not found.", 404)
    dest = parent / name
    dest.write_bytes(data)
    rel = normalize_rel(parent_rel)
    return f"{rel}/{name}".strip("/")


def move_entries(paths: list[str], dest_rel: str) -> int:
    dest = resolve_rel(dest_rel)
    if not dest.is_dir():
        raise DocumentsError("That folder is not there.", 404)
    moved = 0
    for raw in paths:
        src = resolve_rel(raw)
        if not src.exists():
            raise DocumentsError("A selected item is gone.", 404)
        if dest == src or dest.is_relative_to(src):
            raise DocumentsError("Cannot move a folder into itself.")
        target = dest / src.name
        if target.exists():
            raise DocumentsError(f"{src.name} is already in that folder.")
        shutil.move(str(src), str(target))
        moved += 1
    return moved


def delete_entry(rel: str) -> None:
    norm = normalize_rel(rel)
    if not norm:
        raise DocumentsError("The top folder stays.")
    target = resolve_rel(norm)
    if not target.exists():
        raise DocumentsError("Not found.", 404)
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
