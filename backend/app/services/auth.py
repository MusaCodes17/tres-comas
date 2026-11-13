"""Single-user authentication: password hashing, server-side sessions, login throttle.

Job: verify the one password (its scrypt hash lives only in the environment,
INV-3) and manage revocable, sliding server-side sessions.

Rationale: a stolen database must not yield a usable cookie, so only the sha256
of each session token is stored; the raw token exists only in the cookie. The
password hash is read from ``TRES_COMAS_PASSWORD_HASH`` at call time and is
never stored, returned or logged. Datetimes are naive UTC.

Invariants upheld: INV-3 (no secret in code, database, logs or responses).

Ownership: functions here only ``flush``; the caller (router / dependency)
owns the commit.
"""

import base64
import hashlib
import hmac
import logging
import os
import secrets
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import AuthSession

logger = logging.getLogger(__name__)

PASSWORD_HASH_ENV = "TRES_COMAS_PASSWORD_HASH"

SESSION_LIFETIME = timedelta(days=30)
SLIDE_AFTER = timedelta(hours=1)

_SCRYPT_MAXMEM = 64 * 1024 * 1024
_SCRYPT_DKLEN = 32
_SALT_BYTES = 16

THROTTLE_MAX_FAILURES = 5
THROTTLE_WINDOW_SECONDS = 15 * 60

# Monotonic timestamps of recent failed logins. In-memory is fine: one worker
# (AGENTS.md §4.6). A restart clears it, which is acceptable for a single user.
_login_failures: list[float] = []


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str, *, n: int = 2**15, r: int = 8, p: int = 1) -> str:
    """Return ``scrypt$n$r$p$salt_b64$hash_b64`` (urlsafe base64, no padding)."""
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=n, r=r, p=p,
        maxmem=_SCRYPT_MAXMEM, dklen=_SCRYPT_DKLEN,
    )
    return f"scrypt${n}${r}${p}${_b64e(salt)}${_b64e(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    """Check ``password`` against an encoded hash; False (never raises) if malformed."""
    try:
        scheme, n, r, p, salt_b64, hash_b64 = encoded.split("$")
        if scheme != "scrypt":
            return False
        expected = _b64d(hash_b64)
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=_b64d(salt_b64), n=int(n), r=int(r), p=int(p),
            maxmem=_SCRYPT_MAXMEM, dklen=_SCRYPT_DKLEN,
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError, AttributeError):
        return False


def configured_password_hash() -> str:
    """The encoded password hash from the environment, or "" if login is not configured."""
    return os.environ.get(PASSWORD_HASH_ENV, "")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: Session, *, user_agent: str | None) -> str:
    """Create a session row and return the raw token (shown once, only in the cookie)."""
    token = secrets.token_urlsafe(32)
    now = _utcnow()
    db.add(
        AuthSession(
            token_hash=_token_hash(token),
            last_seen_at=now,
            expires_at=now + SESSION_LIFETIME,
            user_agent=user_agent[:256] if user_agent else None,
        )
    )
    db.flush()
    logger.info("auth session created")
    return token


def resolve_session(db: Session, *, token: str) -> AuthSession | None:
    """Return the live session for ``token`` or None (unknown, expired or revoked).

    Slides the session: if ``last_seen_at`` is over an hour old, it is set to
    now and ``expires_at`` moves 30 days ahead; the returned row then has
    ``was_slid(row)`` True so the caller can re-issue the cookie.
    """
    if not token:
        return None
    row = db.scalar(select(AuthSession).where(AuthSession.token_hash == _token_hash(token)))
    if row is None or row.revoked_at is not None:
        return None
    now = _utcnow()
    if row.expires_at <= now:
        return None
    if now - row.last_seen_at > SLIDE_AFTER:
        row.last_seen_at = now
        row.expires_at = now + SESSION_LIFETIME
        db.flush()
        row._slid = True  # plain attribute, not a column; read via was_slid()
    return row


def was_slid(row: AuthSession) -> bool:
    """True if ``resolve_session`` slid this row's expiry during the current request."""
    return bool(getattr(row, "_slid", False))


def revoke_session(db: Session, *, token: str) -> None:
    """Revoke the session for ``token`` (no-op if unknown or already revoked)."""
    row = db.scalar(select(AuthSession).where(AuthSession.token_hash == _token_hash(token)))
    if row is not None and row.revoked_at is None:
        row.revoked_at = _utcnow()
        db.flush()
        logger.info("auth session revoked")


def revoke_all_sessions(db: Session) -> None:
    """Revoke every live session."""
    result = db.execute(
        update(AuthSession).where(AuthSession.revoked_at.is_(None)).values(revoked_at=_utcnow())
    )
    db.flush()
    logger.info("all auth sessions revoked (%s)", result.rowcount)


# --- login throttle -------------------------------------------------------


def _prune_failures(now: float) -> None:
    _login_failures[:] = [t for t in _login_failures if now - t < THROTTLE_WINDOW_SECONDS]


def login_retry_after() -> int | None:
    """Seconds until a login may be tried again, or None if not throttled."""
    now = time.monotonic()
    _prune_failures(now)
    if len(_login_failures) < THROTTLE_MAX_FAILURES:
        return None
    return max(1, int(THROTTLE_WINDOW_SECONDS - (now - _login_failures[0])) + 1)


def record_login_failure() -> None:
    """Count one failed login."""
    _login_failures.append(time.monotonic())
    logger.warning("failed login attempt")


def clear_login_failures() -> None:
    """A successful login clears the counter."""
    _login_failures.clear()


def reset_login_throttle() -> None:
    """Forget all failures (tests)."""
    _login_failures.clear()
