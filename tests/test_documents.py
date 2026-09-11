"""Document library path safety and kinds."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.documents import DocumentsError, list_dir, normalize_rel, resolve_rel, viewer_kind


def test_normalize_blocks_parent():
    with pytest.raises(DocumentsError):
        normalize_rel("../secret")
    assert normalize_rel("NOI Approval/file.pdf") == "NOI Approval/file.pdf"


def test_resolve_stays_in_library():
    root = resolve_rel("")
    assert root.name == "Documents"
    target = resolve_rel("NOI Approval")
    assert target.is_dir()
    with pytest.raises(DocumentsError):
        resolve_rel("..")


def test_viewer_kinds():
    assert viewer_kind(Path("a.pdf")) == "pdf"
    assert viewer_kind(Path("a.DOCX")) == "docx"
    assert viewer_kind(Path("a.xlsx")) == "xlsx"
    assert viewer_kind(Path("a.png")) == "image"
    assert viewer_kind(Path("a.txt")) == "text"
    assert viewer_kind(Path("a.pptx")) == "pptx"
    assert viewer_kind(Path("a.zip")) == "download"


def test_seed_folder_is_listed():
    listing = list_dir("")
    names = [f["name"] for f in listing["folders"]]
    assert "NOI Approval" in names
    inner = list_dir("NOI Approval")
    assert inner["file_count"] >= 3
    assert any(f["kind"] == "pdf" for f in inner["files"])


def test_documents_need_teacher():
    with TestClient(app) as client:
        resp = client.get("/documents", follow_redirects=False)
        assert resp.status_code in {303, 401}
        assert "/login/" in (resp.headers.get("location") or "/login/")
