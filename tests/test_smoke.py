"""Smoke tests for auth doors, grade math, and attendance."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models import AttendanceStatus
from app.services.grades import letter_for


def test_docs_are_off():
    with TestClient(app) as client:
        assert client.get("/docs").status_code in {401, 404}
        assert client.get("/redoc").status_code in {401, 404}
        assert client.get("/openapi.json").status_code in {401, 404}


def test_look_cookie_and_density():
    with TestClient(app) as client:
        resp = client.post(
            "/theme",
            data={"theme": "forest", "density": "compact", "next": "/"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        assert resp.cookies.get("aa_theme") == "forest"
        assert resp.cookies.get("aa_density") == "compact"
        home = client.get("/")
        assert 'data-theme="forest"' in home.text
        assert 'data-density="compact"' in home.text
        assert "Look" in home.text or "Forest" in home.text


def test_login_doors():
    with TestClient(app) as client:
        home = client.get("/", follow_redirects=False)
        assert home.status_code == 200
        assert "Ascendancy" in home.text
        assert home.text.index('data-theme-preview="ascendancy"') < home.text.index('data-theme-preview="giants"')
        teacher = client.get("/login/teacher")
        assert teacher.status_code == 200
        assert "Teacher" in teacher.text
        student = client.get("/login/student")
        assert student.status_code == 200
        assert "Gregory" in student.text


def test_teacher_login_and_desk():
    with TestClient(app) as client:
            resp = client.post(
                "/login/teacher",
                data={"email": "joe_71@yahoo.com", "password": "MkZqqylZDFwB5kYP8LAnjzye", "next": "/teacher"},
                follow_redirects=False,
            )
            assert resp.status_code in {303, 400}
            if resp.status_code == 303:
                assert resp.headers["location"].startswith("/")
                forced = client.get("/settings/password?forced=1")
                assert forced.status_code == 200


def test_student_cannot_use_teacher_door():
    with TestClient(app) as client:
        resp = client.post(
            "/login/teacher",
            data={"email": "gregory@ascendancy.local", "password": "TQEM3fbmpHy4QT7GrJGxmUDJ", "next": "/teacher"},
        )
        assert resp.status_code == 400
        assert "student door" in resp.text.lower() or "Students sign in" in resp.text


def test_letter_scale():
    year = type("Y", (), {"a_min": 90, "b_min": 80, "c_min": 70, "d_min": 60})()
    assert letter_for(95, year) == "A"
    assert letter_for(80, year) == "B"
    assert letter_for(59, year) == "F"
    assert letter_for(None, year) == "—"


def test_attendance_cycle():
    from app.services.attendance import next_status

    assert next_status(None) == AttendanceStatus.PRESENT
    assert next_status(AttendanceStatus.PRESENT) == AttendanceStatus.ABSENT
    assert next_status(AttendanceStatus.OFF) == AttendanceStatus.PRESENT


def test_page_parsing():
    from app.services.pages import assignment_title, normalize_pages, parse_bulk, parse_line

    assert normalize_pages("12-15") == ("12-15", 12)
    assert normalize_pages("12, 18, 20-22") == ("12, 18, 20-22", 12)
    work = parse_line("16-18 work")
    assert work and work.has_work and work.pages == "16-18"
    reading = parse_line("19-21 reading")
    assert reading and reading.has_work is False
    many = parse_bulk("12-15 work\n16-18 reading\n")
    assert len(many) == 2
    book = type("B", (), {"title": "Saxon 5/4"})()
    assert "pp. 12-15" in assignment_title(book, "12-15")
