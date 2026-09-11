"""Local Gemma hop on the Mac — same idea as CCAWEB board minutes."""
from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import settings

RELAY_HEADER = "X-Gemma-Relay-Secret"


class GemmaError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class GemmaStatus:
    available: bool
    mode: str
    model: str
    detail: str


def status() -> GemmaStatus:
    base = (settings.gemma_base_url or "").strip().rstrip("/")
    relay = (settings.gemma_relay_url or "").strip()
    model = (settings.gemma_model or "gemma4:e4b").strip()
    if base:
        return GemmaStatus(True, "direct", model, "Gemma on the Mac is ready.")
    if relay and (settings.gemma_relay_secret or "").strip():
        return GemmaStatus(True, "relay", model, "Gemma relay is ready.")
    return GemmaStatus(False, "off", model, "Gemma is not set up on this site yet.")


def _timeout() -> httpx.Timeout:
    seconds = max(30, int(settings.gemma_timeout_seconds or 180))
    return httpx.Timeout(seconds, connect=10.0)


async def complete(messages: list[dict], temperature: float = 0.2) -> str:
    st = status()
    if not st.available:
        raise GemmaError(st.detail)
    payload = {
        "model": st.model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    headers = {"Content-Type": "application/json"}
    if st.mode == "direct":
        url = (settings.gemma_base_url or "").rstrip("/") + "/v1/chat/completions"
        if (settings.gemma_api_key or "").strip():
            headers["Authorization"] = f"Bearer {settings.gemma_api_key.strip()}"
    else:
        url = settings.gemma_relay_url
        headers[RELAY_HEADER] = settings.gemma_relay_secret
    try:
        async with httpx.AsyncClient(timeout=_timeout()) as client:
            resp = await client.post(url, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        raise GemmaError("Gemma timed out. Try again in a minute.") from exc
    except httpx.HTTPError as exc:
        raise GemmaError("Gemma is not reachable right now. Is the Mac on?") from exc
    if resp.status_code >= 400:
        raise GemmaError("Gemma could not answer. Try another model or type the pages.")
    data = resp.json()
    try:
        return (data["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise GemmaError("Gemma sent a reply we could not read.") from exc
