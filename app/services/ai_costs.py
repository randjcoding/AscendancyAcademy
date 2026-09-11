"""Rough prices so teachers can see an estimate before a call."""
from __future__ import annotations

# USD per 1 million tokens. Update when vendors change prices.
RATES = {
    "gpt-4o-mini": {"in": 0.15, "out": 0.60},
    "gpt-4o": {"in": 2.50, "out": 10.00},
    "claude-haiku-4-5": {"in": 1.00, "out": 5.00},
    "claude-sonnet-4-5": {"in": 3.00, "out": 15.00},
    "claude-sonnet-4-6": {"in": 3.00, "out": 15.00},
    "gemma4:e4b": {"in": 0.0, "out": 0.0},
}

TOKENS_PER_IMAGE = 1600
PROMPT_TOKENS = 700
REPLY_TOKENS = 350

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-5",
    "gemma": "gemma4:e4b",
}


def model_for(provider: str) -> str:
    return DEFAULT_MODELS.get(provider, provider)


def estimate_usd(provider: str, image_count: int, model: str = "") -> dict:
    name = model or model_for(provider)
    rates = RATES.get(name, {"in": 0.0, "out": 0.0})
    images = max(0, int(image_count))
    prompt = PROMPT_TOKENS + images * TOKENS_PER_IMAGE
    completion = REPLY_TOKENS
    usd = (prompt / 1_000_000) * rates["in"] + (completion / 1_000_000) * rates["out"]
    return {
        "provider": provider,
        "model": name,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "usd": round(usd, 4),
        "label": "Free" if usd <= 0 else f"About ${usd:.3f}",
    }


def charge_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    rates = RATES.get(model, {"in": 0.0, "out": 0.0})
    usd = (prompt_tokens / 1_000_000) * rates["in"] + (completion_tokens / 1_000_000) * rates["out"]
    return round(usd, 6)
