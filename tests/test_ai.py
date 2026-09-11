"""API key encryption, cost guesses, and page JSON — no live vendors."""
from app.services.ai_costs import estimate_usd
from app.services.read_pages import _parse_guess
from app.services.secrets import decrypt_secret, encrypt_secret


def test_encrypt_roundtrip():
    blob = encrypt_secret("sk-test-secret")
    assert "sk-test-secret" not in blob
    assert decrypt_secret(blob) == "sk-test-secret"


def test_gemma_estimate_is_free():
    guess = estimate_usd("gemma", 3)
    assert guess["usd"] == 0
    assert "Free" in guess["label"]


def test_openai_estimate_is_positive():
    guess = estimate_usd("openai", 2)
    assert guess["usd"] > 0
    assert guess["model"] == "gpt-4o-mini"


def test_parse_guess_json():
    data = _parse_guess('Here you go\n{"pages": "12-15", "score": 94, "has_work": true, "title": "", "confidence": "high"}')
    assert data["pages"] == "12-15"
    assert data["score"] == 94
    assert _parse_guess("no json") == {}
