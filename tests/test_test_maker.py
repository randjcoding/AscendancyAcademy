"""Test Maker: import, auto-grade, publish->gradebook, retries, and gating."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import Enrollment, Grade, User, UserKind
from app.security import create_session, csrf_token_for
from app.services.clock import house_now


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


def _joe(client: TestClient) -> dict:
    return _sit_as(client, UserKind.TEACHER)


def _greg(client: TestClient) -> dict:
    return _sit_as(client, UserKind.STUDENT)


SAMPLE = {
    "title": "Sample Quiz",
    "questions": [
        {"type": "mc", "prompt": "2 + 2?", "points": 1, "options": ["3", "4", "5"], "correct": [1], "multiple": False},
        {"type": "tf", "prompt": "The sky is blue.", "points": 1, "answer": True},
        {"type": "fill", "prompt": "The capital of France is ____.", "points": 1, "accepted": ["Paris"], "case_sensitive": False},
        {"type": "match", "prompt": "Match the sound.", "points": 2,
         "left": ["cat", "dog"], "right": ["meow", "bark"], "pairs": [[0, 0], [1, 1]]},
    ],
}


def _import(client: TestClient, csrf: str) -> dict:
    resp = client.post("/api/tests/import", json={"csrf": csrf, "json_text": json.dumps(SAMPLE)})
    assert resp.status_code == 200, resp.text
    return resp.json()["test"]


def _publish(client: TestClient, csrf: str, test_id: int, **extra) -> dict:
    stamp = house_now().strftime("%H%M%S%f")
    body = {"csrf": csrf, "new_course_title": f"Test Class {stamp}"}
    body.update(extra)
    resp = client.post(f"/api/tests/{test_id}/publish", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()["test"]


def _correct_answers(take_questions: list[dict]) -> list[dict]:
    answers = []
    for q in take_questions:
        if q["type"] == "mc":
            # option index 1 ("4") is the right one in SAMPLE
            answers.append({"question_id": q["id"], "response": {"selected": [q["options"][1]["id"]]}})
        elif q["type"] == "tf":
            answers.append({"question_id": q["id"], "response": {"answer": True}})
        elif q["type"] == "fill":
            answers.append({"question_id": q["id"], "response": {"text": "Paris"}})
        elif q["type"] == "match":
            pairs = {q["left"][i]["id"]: q["right"][i]["id"] for i in range(len(q["left"]))}
            answers.append({"question_id": q["id"], "response": {"pairs": pairs}})
    return answers


def test_import_normalizes_and_hides_answers():
    with TestClient(app) as client:
        joe = _joe(client)
        test = _import(client, joe["csrf"])
        assert test["points_possible"] == 5
        assert test["question_count"] == 4
        _publish(client, joe["csrf"], test["id"])

        greg = _greg(client)
        take = client.get(f"/api/tests/{test['id']}/take")
        assert take.status_code == 200, take.text
        for q in take.json()["test"]["questions"]:
            # the student payload must never leak the key
            assert "correct" not in q
            assert "answer" not in q
            assert "accepted" not in q
            assert "pairs" not in q


def test_full_credit_submit_writes_gradebook():
    with TestClient(app) as client:
        joe = _joe(client)
        test = _import(client, joe["csrf"])
        published = _publish(client, joe["csrf"], test["id"])
        course_id = published["course_id"]
        assignment_id = published["assignment_id"]

        greg = _greg(client)
        take = client.get(f"/api/tests/{test['id']}/take").json()["test"]
        answers = _correct_answers(take["questions"])
        resp = client.post(f"/api/tests/{test['id']}/submit", json={"csrf": greg["csrf"], "answers": answers})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["attempt"]["percent"] == 100.0
        assert data["attempt"]["score_points"] == 5

        db = SessionLocal()
        try:
            enrollment = db.scalar(
                select(Enrollment).where(Enrollment.course_id == course_id, Enrollment.student_id == 1)
            ) or db.scalar(select(Enrollment).where(Enrollment.course_id == course_id))
            grade = db.scalar(
                select(Grade).where(Grade.assignment_id == assignment_id, Grade.enrollment_id == enrollment.id)
            )
            assert grade is not None
            assert grade.points_earned == 5
        finally:
            db.close()


def test_half_credit_retry_math():
    with TestClient(app) as client:
        joe = _joe(client)
        test = _import(client, joe["csrf"])
        _publish(client, joe["csrf"], test["id"], allow_retries=True, retry_credit="half")

        greg = _greg(client)
        take = client.get(f"/api/tests/{test['id']}/take").json()["test"]
        # answer everything wrong on the first try
        wrong = []
        for q in take["questions"]:
            if q["type"] == "mc":
                wrong.append({"question_id": q["id"], "response": {"selected": [q["options"][0]["id"]]}})
            elif q["type"] == "tf":
                wrong.append({"question_id": q["id"], "response": {"answer": False}})
            elif q["type"] == "fill":
                wrong.append({"question_id": q["id"], "response": {"text": "London"}})
            elif q["type"] == "match":
                wrong.append({"question_id": q["id"], "response": {"pairs": {}}})
        first = client.post(f"/api/tests/{test['id']}/submit", json={"csrf": greg["csrf"], "answers": wrong}).json()
        assert first["attempt"]["score_points"] == 0
        attempt_id = first["attempt"]["id"]

        # now fix them all correctly on retry -> half credit of 5 == 2.5
        fixed = _correct_answers(take["questions"])
        second = client.post(f"/api/tests/attempts/{attempt_id}/retry", json={"csrf": greg["csrf"], "answers": fixed}).json()
        assert second["attempt"]["score_points"] == 2.5


def test_import_rejects_junk():
    with TestClient(app) as client:
        joe = _joe(client)
        resp = client.post("/api/tests/import", json={"csrf": joe["csrf"], "json_text": "not json at all"})
        assert resp.status_code == 400


def test_student_cannot_author():
    with TestClient(app) as client:
        greg = _greg(client)
        assert client.get("/api/tests").status_code == 403
        assert client.post("/api/tests/import", json={"csrf": greg["csrf"], "json_text": json.dumps(SAMPLE)}).status_code == 403
        assert client.get("/api/tests/results/all").status_code == 403
