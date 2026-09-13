"""SMS for this household only — T-Mobile email gateway, Twilio optional."""
from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger("aa.sms")
TMO_GATEWAY = "tmomail.net"


def tmo_gateway_address(to: str) -> str:
    raw = (to or "").strip()
    if not raw:
        return ""
    if "@" in raw:
        return raw
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"{digits}@{TMO_GATEWAY}"
    return raw


def _use_email_gateway() -> bool:
    return settings.sms_enabled and settings.sms_provider.strip().lower() == "email"


def _can_twilio() -> bool:
    return bool(
        settings.sms_enabled
        and settings.sms_provider.strip().lower() != "email"
        and settings.twilio_account_sid
        and settings.twilio_auth_token
        and settings.sms_from
    )


def send_sms(*, to: str, body: str) -> bool:
    to = (to or settings.sms_default_to or "").strip()
    text = (body or "").strip()
    if not text:
        return False

    if _use_email_gateway():
        dest = tmo_gateway_address(to or settings.sms_email_to or settings.sms_default_to)
        if not dest:
            logger.warning("send_sms: no T-Mobile number")
            return False
        from app.services.email import send_email

        return send_email(to=dest, subject="Ascendancy", text_body=text[:1600])

    if not to:
        logger.warning("send_sms: no recipient")
        return False

    if not _can_twilio():
        logger.info("[DEV sms] to=%s body=%s", to, text)
        return True

    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
    try:
        resp = httpx.post(
            url,
            data={"From": settings.sms_from, "To": to, "Body": text},
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            timeout=20.0,
        )
        if resp.status_code in (200, 201):
            return True
        logger.warning("Twilio send failed: %s %s", resp.status_code, resp.text[:300])
        return False
    except Exception:
        logger.exception("Failed to send SMS")
        return False
