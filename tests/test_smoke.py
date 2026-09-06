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


def test_login_doors():
    with TestClient(app) as client:
        home = client.get("/", follow_redirects=False)
        assert home.status_code == 200
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
        assert resp.status_code == 303
        assert resp.headers["location"].startswith("/settings/password")
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
