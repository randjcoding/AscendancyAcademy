"""Guess pages and a score from workbook photos."""
from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass, asdict

import httpx

from app.models import Book, TeacherApiKey
from app.services import ai_costs, gemma, ocr
from app.services.secrets import decrypt_secret

EXTRACT_HINT = """You help a homeschool parent log workbook pages.
Return ONLY JSON with keys:
pages (string like "12-15" or "12" or ""),
score (number or null),
points_possible (number or null),
has_work (true/false),
title (short string or ""),
confidence (high/medium/low).
Use the book title if given. If you cannot tell a field, use empty/null.
Do not invent page numbers."""


@dataclass
class PageGuess:
    pages: str = ""
    score: float | None = None
    points_possible: float | None = None
    has_work: bool = True
    title: str = ""
    confidence: str = "low"
    ocr_text: str = ""
    model: str = ""
    provider: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    usd: float = 0.0
    error: str = ""


def _parse_guess(raw: str) -> dict:
    text = (raw or "").strip()
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _to_guess(data: dict, ocr_text: str, provider: str, model: str, usage: dict) -> PageGuess:
    score = data.get("score")
    try:
        score_val = float(score) if score is not None and str(score) != "" else None
    except (TypeError, ValueError):
        score_val = None
    points = data.get("points_possible")
    try:
        points_val = float(points) if points is not None and str(points) != "" else None
    except (TypeError, ValueError):
        points_val = None
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    return PageGuess(
        pages=str(data.get("pages") or "").strip(),
        score=score_val,
        points_possible=points_val,
        has_work=bool(data.get("has_work", True)),
        title=str(data.get("title") or "").strip(),
        confidence=str(data.get("confidence") or "low"),
        ocr_text=ocr_text,
        model=model,
        provider=provider,
        prompt_tokens=prompt,
        completion_tokens=completion,
        usd=ai_costs.charge_usd(model, prompt, completion),
    )


def _prompt(book: Book | None, ocr_text: str) -> str:
    book_line = f"Book: {book.title}" if book else "Book: unknown"
    if book and book.author:
        book_line += f" by {book.author}"
    ocr_bit = ocr_text or "(no OCR text)"
    return f"{EXTRACT_HINT}\n\n{book_line}\n\nText read from the photos:\n{ocr_bit}"


def _b64(blob: bytes) -> str:
    return base64.b64encode(blob).decode("ascii")


def _mime(blob: bytes) -> str:
    if blob.startswith(b"\x89PNG"):
        return "image/png"
    if blob.startswith(b"GIF"):
        return "image/gif"
    if blob[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if blob.startswith(b"RIFF") and b"WEBP" in blob[:16]:
        return "image/webp"
    return "image/jpeg"


async def _openai(key: str, model: str, book: Book | None, ocr_text: str, images: list[bytes]) -> tuple[str, dict]:
    content: list[dict] = [{"type": "text", "text": _prompt(book, ocr_text)}]
    for blob in images[:6]:
        url = f"data:{_mime(blob)};base64,{_b64(blob)}"
        content.append({"type": "image_url", "image_url": {"url": url}})
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.1,
    }
    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
        )
    if resp.status_code >= 400:
        raise RuntimeError(resp.text[:240] or "OpenAI error")
    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage") or {}
    return text, {
        "prompt_tokens": usage.get("prompt_tokens") or 0,
        "completion_tokens": usage.get("completion_tokens") or 0,
    }


async def _anthropic(key: str, model: str, book: Book | None, ocr_text: str, images: list[bytes]) -> tuple[str, dict]:
    content: list[dict] = []
    for blob in images[:6]:
        content.append(
            {
                "type": "image",
                "source": {"type": "base64", "media_type": _mime(blob), "data": _b64(blob)},
            }
        )
    content.append({"type": "text", "text": _prompt(book, ocr_text)})
    payload = {
        "model": model,
        "max_tokens": 400,
        "messages": [{"role": "user", "content": content}],
    }
    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
        )
    if resp.status_code >= 400:
        # Vision failed — retry text-only with OCR.
        payload["messages"] = [{"role": "user", "content": _prompt(book, ocr_text)}]
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
            )
    if resp.status_code >= 400:
        raise RuntimeError(resp.text[:240] or "Anthropic error")
    data = resp.json()
    parts = data.get("content") or []
    text = ""
    if parts and isinstance(parts[0], dict):
        text = parts[0].get("text") or ""
    usage = data.get("usage") or {}
    return text, {
        "prompt_tokens": usage.get("input_tokens") or 0,
        "completion_tokens": usage.get("output_tokens") or 0,
    }


async def guess_pages(
    *,
    provider: str,
    images: list[bytes],
    book: Book | None,
    key_row: TeacherApiKey | None,
) -> PageGuess:
    ocr_text = ocr.read_images(images)
    model = ai_costs.model_for(provider)
    try:
        if provider == "gemma":
            text = await gemma.complete(
                [{"role": "user", "content": _prompt(book, ocr_text)}],
                temperature=0.1,
            )
            guess = _to_guess(_parse_guess(text), ocr_text, provider, model, {})
            return guess
        if not key_row:
            return PageGuess(ocr_text=ocr_text, provider=provider, model=model, error="Pick a saved key first.")
        secret = decrypt_secret(key_row.secret_enc)
        if not secret:
            return PageGuess(ocr_text=ocr_text, provider=provider, model=model, error="That key could not be read.")
        if provider == "openai":
            text, usage = await _openai(secret, model, book, ocr_text, images)
        elif provider == "anthropic":
            text, usage = await _anthropic(secret, model, book, ocr_text, images)
        else:
            return PageGuess(ocr_text=ocr_text, error="Unknown model.")
        return _to_guess(_parse_guess(text), ocr_text, provider, model, usage)
    except gemma.GemmaError as exc:
        return PageGuess(ocr_text=ocr_text, provider=provider, model=model, error=exc.message)
    except Exception as exc:
        return PageGuess(ocr_text=ocr_text, provider=provider, model=model, error=str(exc)[:240])


def guess_as_dict(guess: PageGuess) -> dict:
    return asdict(guess)
