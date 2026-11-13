"""Shared router dependencies: default-deny authentication and session cookie helpers.

Job: ``require_session`` is installed app-wide in ``create_app()``, so every route,
including any added later, needs a valid session unless its path is in
``PUBLIC_PATHS``. It also re-issues the cookie when the session slides forward.

Invariants upheld: INV-3 (the app is never open; no secret leaves it).
"""

import os
from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import auth as auth_service

PUBLIC_PATHS = frozenset({"/health", "/api/auth/login"})

COOKIE_NAME = "tc_session"
COOKIE_MAX_AGE = int(auth_service.SESSION_LIFETIME.total_seconds())


def _cookie_secure() -> bool:
    # Secure unless explicitly "0" (local http dev only); read at call time.
    return os.environ.get("TRES_COMAS_COOKIE_SECURE") != "0"


def set_session_cookie(response: Response, token: str) -> None:
    """Set the session cookie: HttpOnly, SameSite=Strict, 30 days, Secure by default."""
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=COOKIE_MAX_AGE,
        path="/",
        httponly=True,
        samesite="strict",
        secure=_cookie_secure(),
    )


def clear_session_cookie(response: Response) -> None:
    """Expire the session cookie in the browser."""
    response.delete_cookie(
        COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="strict",
        secure=_cookie_secure(),
    )


def require_session(
    request: Request, response: Response, db: Session = Depends(get_db)
) -> None:
    """Raise 401 unless the request carries a live session (public paths excepted).

    Stores the session on ``request.state.auth_session``. If the session slid
    forward, commits it and re-issues the cookie with a fresh Max-Age.

    Raises:
        HTTPException: 401 when the cookie is missing, unknown, expired or revoked.
    """
    if request.scope["path"] in PUBLIC_PATHS:
        return None
    token = request.cookies.get(COOKIE_NAME, "")
    row = auth_service.resolve_session(db, token=token)
    if row is None:
        db.rollback()
        raise HTTPException(status_code=401, detail="not authenticated")
    if auth_service.was_slid(row):
        db.commit()
        set_session_cookie(response, token)
    request.state.auth_session = row
    return None


@contextmanager
def service_errors(db: Session) -> Iterator[None]:
    """Map service exceptions to HTTP errors and roll back the session.

    LookupError -> 404; ValueError and TypeError -> 400 with the message.
    """
    try:
        yield
    except LookupError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc.args[0] if exc.args else exc)) from exc
    except (ValueError, TypeError) as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
