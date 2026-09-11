"""JSON desk API."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_me_anonymous():
    with TestClient(app) as client:
        resp = client.get("/api/me")
        assert resp.status_code == 200
        body = resp.json()
        assert body["user"] is None
        assert "ascendancy" in body["themes"]
        assert body["site_name"]


def test_api_login_wrong_door_is_json():
    with TestClient(app) as client:
        resp = client.post(
            "/api/login",
            json={
                "door": "teacher",
                "email": "gregory@ascendancy.local",
                "password": "TQEM3fbmpHy4QT7GrJGxmUDJ",
            },
        )
        assert resp.status_code == 400
        assert "error" in resp.json()
        assert "student" in resp.json()["error"].lower()


def test_api_requires_login():
    with TestClient(app) as client:
        resp = client.get("/api/desk")
        assert resp.status_code == 401
        assert resp.headers.get("content-type", "").startswith("application/json")
        assert resp.json()["error"]
