"""Activities catalog, stars, student desk, and admin gating."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.activities.registry import all_activities, get_activity
from app.activities.schema import stars_for
from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import User, UserKind
from app.security import create_session, csrf_token_for
from app.seed import OLD_STUDENT1_EMAILS, _upsert_user


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
        return {"id": user.id, "csrf": csrf_token_for(token)}
    finally:
        db.close()


def test_catalog_has_fifty_unique_capitals():
    catalog = all_activities()
    activity = catalog["us-state-capitals"]
    places = activity.places()
    assert len(places) == 50
    assert len({p.id for p in places}) == 50
    assert len({p.capital for p in places}) == 50
    assert set(activity.modes) >= {"study", "find_on_map", "name_the_capital", "flashcards"}


def test_star_thresholds():
    activity = get_activity("us-state-capitals")
    assert activity
    c = activity.passing_criteria
    assert stars_for(c, finished=False, accuracy=100) == 0
    assert stars_for(c, finished=True, accuracy=40) == 1
    assert stars_for(c, finished=True, accuracy=80) == 2
    assert stars_for(c, finished=True, accuracy=100) == 3


def test_student_can_play_and_record():
    with TestClient(app) as client:
        greg = _sit_as(client, UserKind.STUDENT)
        listing = client.get("/api/activities")
        assert listing.status_code == 200, listing.text
        assert listing.json()["activities"]
        one = client.get("/api/activities/us-state-capitals")
        assert one.status_code == 200
        assert one.json()["activity"]["content"][0]["capital"]
        saved = client.post(
            "/api/activities/us-state-capitals/attempt",
            json={"csrf": greg["csrf"], "mode": "find_on_map", "score": 40, "total": 50, "time_taken_seconds": 120},
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["stars_earned"] == 2
        attend = client.get("/api/attendance")
        assert attend.status_code == 200


def test_student_blocked_from_admin_and_keys():
    with TestClient(app) as client:
        greg = _sit_as(client, UserKind.STUDENT)
        assert client.get("/api/admin/people").status_code == 403
        assert client.post("/api/keys", json={"csrf": greg["csrf"], "name": "Nope", "provider": "openai", "secret": "sk-test"}).status_code == 403


def test_gregory_remap_is_idempotent():
    db = SessionLocal()
    try:
        user = _upsert_user(
            db,
            email="gregorydifede@gmail.com",
            first_name="Gregory",
            last_name="DiFede",
            password="Password123456",
            kind=UserKind.STUDENT,
            is_admin=False,
            role="student",
            previous_emails=OLD_STUDENT1_EMAILS,
            apply_password_on_remap=True,
        )
        again = _upsert_user(
            db,
            email="gregorydifede@gmail.com",
            first_name="Gregory",
            last_name="DiFede",
            password="Password123456",
            kind=UserKind.STUDENT,
            is_admin=False,
            role="student",
            previous_emails=OLD_STUDENT1_EMAILS,
            apply_password_on_remap=True,
        )
        assert user.id == again.id
        assert again.email == "gregorydifede@gmail.com"
        db.rollback()
    finally:
        db.close()
