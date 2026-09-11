"""Encrypt teacher API keys with the site secret."""
from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _fernet() -> Fernet:
    digest = hashlib.sha256((settings.secret_key or "dev").encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(raw: str) -> str:
    return _fernet().encrypt((raw or "").encode("utf-8")).decode("ascii")


def decrypt_secret(blob: str) -> str:
    try:
        return _fernet().decrypt((blob or "").encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""
