"""Password hashing, sessions, CSRF."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from passlib.context import CryptContext
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import AccountStatus, AuthEvent, SessionRow, User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

FAILURE_MESSAGE = "Invalid email or password."


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def utcnow() -> datetime:
    return datetime.utcnow()


def client_ip(request) -> str:
    forwarded = request.headers.get("CF-Connecting-IP") or request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return ""


def log_auth_event(
    db: Session,
    *,
    event_type: str,
    email: str | None = None,
    user_id: int | None = None,
    ip_address: str | None = None,
    detail: str | None = None,
) -> None:
    db.add(
        AuthEvent(
            user_id=user_id,
            email=email,
            event_type=event_type,
            ip_address=ip_address,
            detail=detail,
        )
    )


def is_locked(user: User) -> bool:
    return bool(user.locked_until and user.locked_until > utcnow())


def create_session(db: Session, user: User, request) -> str:
    token = new_token()
    expires = utcnow() + timedelta(hours=settings.session_ttl_hours)
    db.add(
        SessionRow(
            token_hash=token_hash(token),
            user_id=user.id,
            expires_at=expires,
            user_agent=(request.headers.get("user-agent") or "")[:512],
            ip_address=client_ip(request),
        )
    )
    db.commit()
    return token


def delete_session(db: Session, token: str | None) -> None:
    if not token:
        return
    db.execute(delete(SessionRow).where(SessionRow.token_hash == token_hash(token)))
    db.commit()


def delete_all_sessions(db: Session, user_id: int) -> None:
    db.execute(delete(SessionRow).where(SessionRow.user_id == user_id))
    db.commit()


def get_user_by_session(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    row = db.scalar(select(SessionRow).where(SessionRow.token_hash == token_hash(token)))
    if not row or row.expires_at < utcnow():
        if row:
            db.delete(row)
            db.commit()
        return None
    user = db.get(User, row.user_id)
    if not user or user.status != AccountStatus.ACTIVE:
        return None
    return user


def authenticate(db: Session, email: str, password: str, request) -> User | None:
    email_norm = email.lower().strip()
    user = db.scalar(select(User).where(User.email == email_norm))
    ip = client_ip(request)

    if not user or not user.password_hash:
        log_auth_event(db, event_type="login_failed", email=email_norm, ip_address=ip)
        db.commit()
        return None

    if is_locked(user):
        log_auth_event(
            db,
            event_type="login_locked",
            email=email_norm,
            user_id=user.id,
            ip_address=ip,
        )
        db.commit()
        return None

    if not verify_password(password, user.password_hash):
        user.failed_login_count += 1
        if user.failed_login_count >= settings.max_failed_attempts:
            user.locked_until = utcnow() + timedelta(minutes=settings.lockout_minutes)
            user.failed_login_count = 0
            log_auth_event(
                db,
                event_type="account_locked",
                email=email_norm,
                user_id=user.id,
                ip_address=ip,
            )
        log_auth_event(
            db,
            event_type="login_failed",
            email=email_norm,
            user_id=user.id,
            ip_address=ip,
        )
        db.commit()
        return None

    user.failed_login_count = 0
    user.locked_until = None
    log_auth_event(
        db,
        event_type="login_success",
        email=email_norm,
        user_id=user.id,
        ip_address=ip,
    )
    db.commit()
    return user


def csrf_token_for(session_token: str) -> str:
    return hmac.new(
        settings.secret_key.encode("utf-8"),
        session_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_csrf(session_token: str | None, submitted: str | None) -> bool:
    if settings.testing:
        return True
    if not session_token or not submitted:
        return False
    expected = csrf_token_for(session_token)
    return hmac.compare_digest(expected, submitted.strip())
