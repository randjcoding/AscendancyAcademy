"""Notes visibility, save conflicts, reminders, and the due-today board."""
from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import (
    Assignment,
    Enrollment,
    GradeCategory,
    ReminderItem,
    ReminderJob,
    ShareScope,
    Task,
    User,
    UserKind,
)
from app.security import create_session, csrf_token_for
from app.services.clock import house_now, house_today
from app.services.reminder_compose import compose, unchecked_lines_from_html


class _Req:
    headers: dict = {}
    client = None


def _sit_as(client: TestClient, kind: UserKind) -> dict:
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.kind == kind).order_by(User.id))
        assert user
        token = create_session(db, user, _Req())
        client.cookies.set(settings.session_cookie_name, token)
        return {"id": user.id, "csrf": csrf_token_for(token), "is_teacher": user.is_teacher}
    finally:
        db.close()


def _joe(client: TestClient) -> dict:
    return _sit_as(client, UserKind.TEACHER)


def _greg(client: TestClient) -> dict:
    return _sit_as(client, UserKind.STUDENT)


def test_unchecked_lines_skip_checked_boxes():
    html = """
    <ul data-type="taskList">
      <li data-type="taskItem" data-checked="true">Done one</li>
      <li data-type="taskItem" data-checked="false">Still open</li>
    </ul>
    """
    assert unchecked_lines_from_html(html) == ["Still open"]


def test_gregory_cannot_read_joe_personal_but_can_read_school():
    with TestClient(app) as client:
        joe = _joe(client)
        tree = client.get("/api/notes/tree")
        assert tree.status_code == 200
        books = tree.json()["notebooks"]
        personal = next(b for b in books if b["scope"] == ShareScope.PERSONAL)
        school = next(b for b in books if b["scope"] == ShareScope.SCHOOL)
        mine = client.post(
            "/api/notes/pages",
            json={"notebook_id": personal["id"], "title": "Joe only", "csrf": joe["csrf"]},
        )
        assert mine.status_code == 200, mine.text
        ours = client.post(
            "/api/notes/pages",
            json={"notebook_id": school["id"], "title": "School page", "csrf": joe["csrf"]},
        )
        assert ours.status_code == 200, ours.text
        personal_id = mine.json()["page"]["id"]
        school_id = ours.json()["page"]["id"]

        greg = _greg(client)
        hidden = client.get(f"/api/notes/pages/{personal_id}")
        assert hidden.status_code == 403
        open_page = client.get(f"/api/notes/pages/{school_id}")
        assert open_page.status_code == 200
        assert open_page.json()["page"]["title"] == "School page"


def test_gregory_reads_only_his_class_notes():
    with TestClient(app) as client:
        joe = _joe(client)
        stamp = house_now().strftime("%H%M%S%f")
        his = client.post("/api/courses", json={"title": f"ELA Notes {stamp}", "csrf": joe["csrf"]})
        other = client.post("/api/courses", json={"title": f"Hidden Notes {stamp}", "csrf": joe["csrf"]})
        assert his.status_code == 200 and other.status_code == 200
        hidden_course_id = other.json()["id"]
        db = SessionLocal()
        try:
            for row in db.scalars(select(Enrollment).where(Enrollment.course_id == hidden_course_id)).all():
                db.delete(row)
            db.commit()
        finally:
            db.close()

        tree = client.get("/api/notes/tree")
        books = tree.json()["notebooks"]
        ela = next(b for b in books if b["course_id"] == his.json()["id"])
        hidden_nb = next(b for b in books if b["course_id"] == hidden_course_id)
        ela_page = client.post(
            "/api/notes/pages",
            json={"notebook_id": ela["id"], "title": "ELA notes", "csrf": joe["csrf"]},
        )
        hidden_page = client.post(
            "/api/notes/pages",
            json={"notebook_id": hidden_nb["id"], "title": "Not for Greg", "csrf": joe["csrf"]},
        )
        assert ela_page.status_code == 200
        assert hidden_page.status_code == 200

        greg = _greg(client)
        assert client.get(f"/api/notes/pages/{ela_page.json()['page']['id']}").status_code == 200
        assert client.get(f"/api/notes/pages/{hidden_page.json()['page']['id']}").status_code == 403


def test_note_save_409_does_not_clobber():
    with TestClient(app) as client:
        joe = _joe(client)
        tree = client.get("/api/notes/tree").json()["notebooks"]
        personal = next(b for b in tree if b["scope"] == ShareScope.PERSONAL)
        created = client.post(
            "/api/notes/pages",
            json={"notebook_id": personal["id"], "title": "Conflict", "csrf": joe["csrf"]},
        )
        page_id = created.json()["page"]["id"]
        first = client.post(
            f"/api/notes/pages/{page_id}/save",
            json={"csrf": joe["csrf"], "revision": 0, "title": "V1", "body_html": "<p>one</p>"},
        )
        assert first.status_code == 200
        clash = client.post(
            f"/api/notes/pages/{page_id}/save",
            json={"csrf": joe["csrf"], "revision": 0, "title": "V2 wipe", "body_html": "<p>wipe</p>"},
        )
        assert clash.status_code == 409
        page = client.get(f"/api/notes/pages/{page_id}").json()["page"]
        assert page["title"] == "V1"
        assert "wipe" not in (page["body_html"] or "")


def test_reminder_post_needs_csrf():
    with TestClient(app) as client:
        _joe(client)
        resp = client.post(
            "/api/reminders",
            json={"name": "Ping", "send_at": house_now().isoformat(timespec="minutes")},
        )
        assert resp.status_code == 403


def test_note_post_needs_csrf():
    with TestClient(app) as client:
        _joe(client)
        tree = client.get("/api/notes/tree").json()["notebooks"]
        personal = next(b for b in tree if b["scope"] == ShareScope.PERSONAL)
        resp = client.post("/api/notes/pages", json={"notebook_id": personal["id"], "title": "No token"})
        assert resp.status_code == 403


def test_reminder_compose_drops_completed():
    db = SessionLocal()
    try:
        user = db.scalar(select(User).order_by(User.id))
        assert user
        job = ReminderJob(user_id=user.id, name="Chores", send_at=house_now(), recipient=user.email)
        db.add(job)
        db.flush()
        task = Task(
            created_by_user_id=user.id,
            owner_user_id=user.id,
            title="Done chore",
            completed=True,
            scope=ShareScope.PERSONAL,
        )
        db.add(task)
        db.flush()
        job.items.append(ReminderItem(item_type="task", item_id=task.id, sort_order=0))
        message = compose(db, job)
        assert "All caught up" in message["text"]
        db.rollback()
    finally:
        db.close()


def test_board_today_includes_overdue_excludes_tomorrow():
    with TestClient(app) as client:
        joe = _joe(client)
        course = client.post("/api/courses", json={"title": f"Board Class {house_now().strftime('%H%M%S%f')}", "csrf": joe["csrf"]})
        assert course.status_code == 200
        course_id = course.json()["id"]
        today = house_today()
        db = SessionLocal()
        try:
            cat = db.scalar(select(GradeCategory).where(GradeCategory.course_id == course_id))
            db.add(
                Assignment(
                    course_id=course_id,
                    category_id=cat.id,
                    title="Late pages",
                    due_date=today - timedelta(days=1),
                )
            )
            db.add(
                Assignment(
                    course_id=course_id,
                    category_id=cat.id,
                    title="Tomorrow pages",
                    due_date=today + timedelta(days=1),
                )
            )
            db.add(
                Task(
                    created_by_user_id=joe["id"],
                    owner_user_id=joe["id"],
                    title="Open today",
                    scope=ShareScope.SCHOOL,
                    due_at=house_now(),
                )
            )
            db.add(
                Task(
                    created_by_user_id=joe["id"],
                    owner_user_id=joe["id"],
                    title="Tomorrow chore",
                    scope=ShareScope.SCHOOL,
                    due_at=house_now() + timedelta(days=1),
                )
            )
            db.commit()
        finally:
            db.close()

        board = client.get("/api/board/today")
        assert board.status_code == 200, board.text
        titles = [i["title"] for i in board.json()["items"]]
        assert "Late pages" in titles
        assert "Open today" in titles
        assert "Tomorrow pages" not in titles
        assert "Tomorrow chore" not in titles
        late = [i["title"] for i in board.json()["late"]]
        assert "Late pages" in late
