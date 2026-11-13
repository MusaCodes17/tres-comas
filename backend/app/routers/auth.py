"""Login, logout and session status routes (P-5).

Job: HTTP only. Password and session rules live in ``services/auth.py``.
The login route is public (see ``deps.PUBLIC_PATHS``); the rest need a session.

Invariants upheld: INV-3 (no response ever contains the hash or password).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.deps import COOKIE_NAME, clear_session_cookie, set_session_cookie
from app.services import auth as auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


@router.post("/login", status_code=204, response_class=Response)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)) -> Response:
    """Verify the password and start a session (cookie set on success).

    Raises:
        HTTPException: 503 if no password hash is configured, 429 when throttled,
            401 for a wrong password.
    """
    encoded = auth_service.configured_password_hash()
    if not encoded:
        raise HTTPException(status_code=503, detail="login not configured")
    retry_after = auth_service.login_retry_after()
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="too many failed logins",
            headers={"Retry-After": str(retry_after)},
        )
    if not auth_service.verify_password(body.password, encoded):
        auth_service.record_login_failure()
        raise HTTPException(status_code=401, detail="invalid password")
    auth_service.clear_login_failures()
    token = auth_service.create_session(db, user_agent=request.headers.get("user-agent"))
    db.commit()
    response = Response(status_code=204)
    set_session_cookie(response, token)
    return response


@router.post("/logout", status_code=204, response_class=Response)
def logout(request: Request, db: Session = Depends(get_db)) -> Response:
    """Revoke the current session and clear the cookie."""
    auth_service.revoke_session(db, token=request.cookies.get(COOKIE_NAME, ""))
    db.commit()
    response = Response(status_code=204)
    clear_session_cookie(response)
    return response


@router.post("/logout-all", status_code=204, response_class=Response)
def logout_all(db: Session = Depends(get_db)) -> Response:
    """Revoke every session (this one included) and clear the cookie."""
    auth_service.revoke_all_sessions(db)
    db.commit()
    response = Response(status_code=204)
    clear_session_cookie(response)
    return response


@router.get("/me")
def me(request: Request) -> dict:
    """Report that the caller is authenticated and when the session expires (UTC)."""
    session = request.state.auth_session
    return {"authenticated": True, "expires_at": session.expires_at.isoformat() + "Z"}
