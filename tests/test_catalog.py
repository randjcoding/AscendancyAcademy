"""School catalog links and list-view cookie."""
from fastapi.testclient import TestClient

from app.main import app
from app.services.catalog import book_fields, linked


def test_books_page_needs_teacher():
    with TestClient(app) as client:
        resp = client.get("/books", follow_redirects=False)
        assert resp.status_code in {303, 401}
        assert "/login/" in (resp.headers.get("location") or "/login/")


def test_photos_page_needs_teacher():
    with TestClient(app) as client:
        resp = client.get("/photos", follow_redirects=False)
        assert resp.status_code in {303, 401}


def test_view_cookie():
    with TestClient(app) as client:
        resp = client.post("/view", data={"view": "table", "next": "/"}, follow_redirects=False)
        assert resp.status_code == 303
        assert resp.cookies.get("aa_view") == "table"


def test_book_fields_need_a_title():
    fields = book_fields("", "", "", "other", "", "", "")
    assert fields["title"] == ""


def test_linked_helper():
    book = type("B", (), {"course_links": [type("L", (), {"course_id": 3})()]})()
    assert linked(book, 3)
    assert not linked(book, 9)
