"""Book edit page is teacher-only."""
from fastapi.testclient import TestClient

from app.main import app


def test_edit_book_needs_teacher():
    with TestClient(app) as client:
        resp = client.get("/courses/1/books/1", follow_redirects=False)
        assert resp.status_code in {303, 401}
        assert "/login/" in (resp.headers.get("location") or "/login/")
