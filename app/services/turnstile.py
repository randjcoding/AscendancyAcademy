"""Cloudflare Turnstile helpers."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from starlette.requests import Request

from app.config import settings

logger = logging.getLogger("app.turnstile")
SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
FAILURE_MESSAGE = (
    "Please complete the security check and try again. "
    "If the checkbox never appears, refresh the page."
)


def turnstile_active() -> bool:
    if not settings.turnstile_enabled:
        return False
    return bool(
        (settings.turnstile_site_key or "").strip()
        and (settings.turnstile_secret_key or "").strip()
    )


def is_local_host(request: Request) -> bool:
    host = (request.url.hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def turnstile_required(request: Request) -> bool:
    if not turnstile_active():
        return False
    if settings.testing:
        return False
    if is_local_host(request):
        return False
    return True


async def turnstile_token_from_request(request: Request) -> str:
    header = (request.headers.get("CF-Turnstile-Response") or "").strip()
    if header:
        return header
    try:
        form = await request.form()
    except Exception:
        return ""
    for key in ("cf-turnstile-response", "cf_turnstile_response"):
        val = form.get(key)
        if val:
            return str(val).strip()
    return ""


def verify_turnstile(request: Request, token: str | None = None) -> bool:
    if not turnstile_required(request):
        return True

    resolved = (token or "").strip()
    if not resolved:
        logger.warning("Turnstile token missing on %s", request.url.path)
        return False

    secret = (settings.turnstile_secret_key or "").strip()
    form_data: dict[str, str] = {"secret": secret, "response": resolved}
    remoteip = request.headers.get("CF-Connecting-IP")
    if not remoteip and request.client:
        remoteip = request.client.host
    if remoteip:
        form_data["remoteip"] = remoteip

    body = urllib.parse.urlencode(form_data).encode("utf-8")
    try:
        req = urllib.request.Request(
            SITEVERIFY_URL,
            data=body,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except Exception:
            logger.error("Turnstile siteverify HTTP %s", exc.code)
            return bool(settings.turnstile_fail_open)
    except (
        urllib.error.URLError,
        TimeoutError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        logger.error("Turnstile siteverify failed: %s", exc)
        return bool(settings.turnstile_fail_open)

    if not payload.get("success"):
        logger.warning(
            "Turnstile rejected on %s: %s",
            request.url.path,
            payload.get("error-codes") or payload,
        )
        return False
    return True
