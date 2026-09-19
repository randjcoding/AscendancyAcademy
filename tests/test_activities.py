"""Activities catalog, stars, student desk, and admin gating."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.activities.path_regions import PATH_GAMES, all_ids
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
    all_activities.cache_clear()
    catalog = all_activities()
    activity = catalog["us-state-capitals"]
    places = activity.places()
    assert len(places) == 50
    assert len({p.id for p in places}) == 50
    assert len({p.capital for p in places}) == 50
    assert set(activity.modes) >= {
        "study",
        "find_on_map",
        "find_the_state",
        "name_the_capital",
        "flashcards",
        "quiz",
        "match",
        "type_it",
        "city_trap",
        "neighbor_hunt",
    }
    assert all(p.trap_city for p in places)
    assert {p.id for p in places} == set(all_ids())
    assert {p.id for p in places if p.path_region == "new_england"} == {"ME", "NH", "VT", "MA", "RI", "CT"}
    assert next(p for p in places if p.id == "UT").path_region == "mountain_west"


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
        quiz = client.post(
            "/api/activities/us-state-capitals/attempt",
            json={"csrf": greg["csrf"], "mode": "quiz", "score": 8, "total": 10, "time_taken_seconds": 40, "detail": {"batch": 10}},
        )
        assert quiz.status_code == 200, quiz.text
        match = client.post(
            "/api/activities/us-state-capitals/attempt",
            json={"csrf": greg["csrf"], "mode": "match", "score": 5, "total": 5, "time_taken_seconds": 30, "detail": {"batch": 5}},
        )
        assert match.status_code == 200, match.text
        assert match.json()["stars_earned"] == 3
        typed = client.post(
            "/api/activities/us-state-capitals/attempt",
            json={
                "csrf": greg["csrf"],
                "mode": "type_it",
                "score": 3,
                "total": 5,
                "time_taken_seconds": 20,
                "detail": {
                    "batch": 5,
                    "items": [
                        {"id": "NY", "correct": False},
                        {"id": "IL", "correct": False},
                        {"id": "TX", "correct": True},
                    ],
                },
            },
        )
        assert typed.status_code == 200, typed.text
        struggle = client.get("/api/activities/us-state-capitals/struggle")
        assert struggle.status_code == 200, struggle.text
        need = {row["id"] for row in struggle.json()["need_work"]}
        assert "NY" in need
        assert "IL" in need
        find_state = client.post(
            "/api/activities/us-state-capitals/attempt",
            json={"csrf": greg["csrf"], "mode": "find_the_state", "score": 50, "total": 50, "time_taken_seconds": 80},
        )
        assert find_state.status_code == 200, find_state.text
        assert find_state.json()["stars_earned"] == 3
        attend = client.get("/api/attendance")
        assert attend.status_code == 200
        notes = client.get("/api/notes/tree")
        assert notes.status_code == 200
        tasks = client.get("/api/tasks?filter=mine")
        assert tasks.status_code == 200
        home = client.get("/api/student")
        assert home.status_code == 200


def test_student_blocked_from_admin_and_keys():
    with TestClient(app) as client:
        greg = _sit_as(client, UserKind.STUDENT)
        assert client.get("/api/admin/people").status_code == 403
        assert client.post("/api/keys", json={"csrf": greg["csrf"], "name": "Nope", "provider": "openai", "secret": "sk-test"}).status_code == 403
        assert client.get("/api/courses").status_code == 403
        assert client.get("/api/tests").status_code == 403


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


def test_learning_path_locks_later_regions():
    with TestClient(app) as client:
        greg = _sit_as(client, UserKind.STUDENT)
        intro = client.post(
            "/api/activities/us-state-capitals/path",
            json={"csrf": greg["csrf"], "region": "new_england", "intro_done": True},
        )
        assert intro.status_code == 200, intro.text
        sneak = client.post(
            "/api/activities/us-state-capitals/attempt",
            json={
                "csrf": greg["csrf"],
                "mode": "find_the_state",
                "score": 8,
                "total": 8,
                "detail": {"path": {"region": "mountain_west", "first_pass": 100}},
            },
        )
        assert sneak.status_code == 200, sneak.text
        path = client.get("/api/activities/us-state-capitals/path").json()["path"]
        mountain = next(row for row in path["regions"] if row["id"] == "mountain_west")
        assert mountain["unlocked"] is False
        assert not mountain["games"]["find_the_state"]
        for mode in PATH_GAMES:
            saved = client.post(
                "/api/activities/us-state-capitals/attempt",
                json={
                    "csrf": greg["csrf"],
                    "mode": mode,
                    "score": 6,
                    "total": 6,
                    "detail": {"path": {"region": "new_england", "first_pass": 100}},
                },
            )
            assert saved.status_code == 200, saved.text
        path2 = client.get("/api/activities/us-state-capitals/path").json()["path"]
        ne = next(row for row in path2["regions"] if row["id"] == "new_england")
        assert ne["passed"] is True
        mid = next(row for row in path2["regions"] if row["id"] == "mid_atlantic")
        assert mid["unlocked"] is True
        south = next(row for row in path2["regions"] if row["id"] == "south")
        assert south["unlocked"] is False


def test_spell_help_defaults_on_and_parent_can_turn_off():
    with TestClient(app) as client:
        greg = _sit_as(client, UserKind.STUDENT)
        me = client.get("/api/me")
        assert me.status_code == 200
        assert me.json()["user"]["spell_help"] is True
        one = client.get("/api/activities/us-state-capitals")
        assert one.status_code == 200
        prefs = one.json()["practice_prefs"]
        assert prefs["user_id"] == greg["id"]
        assert prefs["spell_help"] is True
        saved = client.post(
            "/api/profile",
            json={"csrf": greg["csrf"], "spell_help": False},
        )
        assert saved.status_code == 200
        assert saved.json()["user"]["spell_help"] is False
        joe = _sit_as(client, UserKind.TEACHER)
        activity = client.get("/api/activities/us-state-capitals")
        assert activity.json()["practice_prefs"]["spell_help"] is False
        flipped = client.post(
            "/api/profile",
            json={"csrf": joe["csrf"], "spell_help": True, "user_id": greg["id"]},
        )
        assert flipped.status_code == 200
        assert flipped.json()["spell_help"] is True
        _sit_as(client, UserKind.STUDENT)
        again = client.get("/api/me")
        assert again.json()["user"]["spell_help"] is True
        sneak = client.post(
            "/api/profile",
            json={"csrf": again.json()["user"]["csrf"], "spell_help": False, "user_id": joe["id"]},
        )
        assert sneak.status_code == 200
        assert sneak.json()["user"]["spell_help"] is False
        joe_me = _sit_as(client, UserKind.TEACHER)
        teacher = client.get("/api/me")
        assert teacher.json()["user"]["id"] == joe_me["id"]
        assert teacher.json()["user"]["spell_help"] is True
        restore = client.post(
            "/api/profile",
            json={"csrf": joe_me["csrf"], "spell_help": True, "user_id": greg["id"]},
        )
        assert restore.status_code == 200
        assert restore.json()["spell_help"] is True
