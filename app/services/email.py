"""SMTP helper for reminder mail."""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Iterable

from app.config import settings

logger = logging.getLogger("aa.email")


def _can_send() -> bool:
    return bool(
        settings.mail_enabled
        and settings.smtp_host
        and settings.smtp_user
        and settings.smtp_password
        and settings.mail_from_address
    )


def send_email(
    *,
    to: str | Iterable[str],
    subject: str,
    text_body: str,
    html_body: str | None = None,
) -> bool:
    recipients = [to] if isinstance(to, str) else [r for r in to if r]
    if not recipients:
        return False

    if not _can_send():
        logger.info("[DEV email] to=%s subject=%s\n%s", recipients, subject, text_body)
        return True

    msg = EmailMessage()
    msg["From"] = settings.mail_from_header
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    password = settings.smtp_password.replace(" ", "")
    try:
        context = ssl.create_default_context()
        if settings.smtp_ssl:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context) as smtp:
                smtp.login(settings.smtp_user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
                smtp.starttls(context=context)
                smtp.login(settings.smtp_user, password)
                smtp.send_message(msg)
        return True
    except Exception:
        logger.exception("Email send failed")
        return False
