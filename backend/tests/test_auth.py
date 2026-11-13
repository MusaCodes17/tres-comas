"""Auth tests (T4, P-5): password hashing, sessions, throttle, default deny, INV-3."""

import base64
import hashlib
import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import select

from app.main import app
from app.models import AuthSession
from app.routers.deps import PUBLIC_PATHS
from app.services.auth import hash_password, verify_password
from tests.conftest import TEST_PASSWORD

LOGIN = "/api/auth/login"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _login(client, password=TEST_PASSWORD):
    return client.post(LOGIN, json={"password": password})


def _row_for(session, token: str) -> AuthSession:
    session.expire_all()
    digest = hashlib.sha256(token.encode()).hexdigest()
    return session.scalar(select(AuthSession).where(AuthSession.token_hash == digest))


# --- hashing --------------------------------------------------------------


def test_hash_verify_round_trip():
    encoded = hash_password("a long enough password", n=2**10)
    assert verify_password("a long enough password", encoded) is True
    assert verify_password("another password", encoded) is False


def test_verify_malformed_hash_returns_false():
    for bad in ("", "garbage", "scrypt$1$2$3", "bcrypt$1024$8$1$aa$bb",
                "scrypt$x$8$1$aa$bb", "scrypt$1024$8$1$!!!$???", "scrypt$3$8$1$aa$bb"):
        assert verify_password("whatever", bad) is False


def test_hash_format():
    scheme, n, r, p, salt, digest = hash_password("pw", n=2**10).split("$")
    assert (scheme, n, r, p) == ("scrypt", "1024", "8", "1")
    assert "=" not in salt + digest
    assert len(base64.urlsafe_b64decode(salt + "=" * (-len(salt) % 4))) == 16
    assert len(base64.urlsafe_b64decode(digest + "=" * (-len(digest) % 4))) == 32


def test_hash_uses_fresh_salt():
    assert hash_password("pw", n=2**10) != hash_password("pw", n=2**10)


# --- login / me -----------------------------------------------------------


def test_login_success_sets_cookie_and_stores_only_hash(api_client, session):
    response = _login(api_client)
    assert response.status_code == 204
    set_cookie = response.headers["set-cookie"]
    assert "tc_session=" in set_cookie
    assert "httponly" in set_cookie.lower()
    assert "samesite=strict" in set_cookie.lower()
    assert "Max-Age=2592000" in set_cookie
    assert "Path=/" in set_cookie

    me = api_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["authenticated"] is True
    assert me.json()["expires_at"]

    token = api_client.cookies.get("tc_session")
    rows = session.scalars(select(AuthSession)).all()
    assert len(rows) == 1
    assert rows[0].token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in rows[0].token_hash
    assert rows[0].revoked_at is None


def test_login_wrong_password_is_401(api_client):
    response = _login(api_client, "not the password")
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid password"}
    assert "set-cookie" not in response.headers


def test_login_not_configured_is_503(api_client, monkeypatch):
    monkeypatch.delenv("TRES_COMAS_PASSWORD_HASH")
    assert _login(api_client).status_code == 503
    monkeypatch.setenv("TRES_COMAS_PASSWORD_HASH", "")
    response = _login(api_client)
    assert response.status_code == 503
    assert response.json() == {"detail": "login not configured"}
    assert api_client.get("/api/auth/me").status_code == 401


def test_login_throttle_after_five_failures(api_client):
    for _ in range(5):
        assert _login(api_client, "wrong").status_code == 401
    assert _login(api_client, "wrong").status_code == 429
    blocked = _login(api_client)  # correct password, still throttled
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0
    assert api_client.get("/api/auth/me").status_code == 401


def test_login_success_clears_failure_counter(api_client):
    for _ in range(4):
        assert _login(api_client, "wrong").status_code == 401
    assert _login(api_client).status_code == 204
    for _ in range(4):
        assert _login(api_client, "wrong").status_code == 401


# --- logout ---------------------------------------------------------------


def test_logout_revokes_session(authed_client, session):
    token = authed_client.cookies.get("tc_session")
    response = authed_client.post("/api/auth/logout")
    assert response.status_code == 204
    assert _row_for(session, token).revoked_at is not None
    # Replay the old cookie explicitly: the server must refuse it.
    authed_client.cookies.set("tc_session", token)
    assert authed_client.get("/api/auth/me").status_code == 401


def test_logout_all_revokes_every_session(authed_client, session):
    first = authed_client.cookies.get("tc_session")
    assert _login(authed_client).status_code == 204
    second = authed_client.cookies.get("tc_session")
    assert first != second

    assert authed_client.post("/api/auth/logout-all").status_code == 204
    assert all(r.revoked_at is not None for r in session.scalars(select(AuthSession)).all())
    for token in (first, second):
        authed_client.cookies.set("tc_session", token)
        assert authed_client.get("/api/auth/me").status_code == 401


# --- lifetime -------------------------------------------------------------


def test_expired_session_is_401(authed_client, session):
    row = _row_for(session, authed_client.cookies.get("tc_session"))
    row.expires_at = _now() - timedelta(minutes=1)
    session.commit()
    assert authed_client.get("/api/auth/me").status_code == 401


def test_session_slides_when_last_seen_is_over_an_hour_old(authed_client, session):
    token = authed_client.cookies.get("tc_session")
    row = _row_for(session, token)
    row.last_seen_at = _now() - timedelta(hours=2)
    row.expires_at = _now() + timedelta(days=10)
    old_expiry = row.expires_at
    session.commit()

    response = authed_client.get("/api/auth/me")
    assert response.status_code == 200
    assert "Max-Age=2592000" in response.headers["set-cookie"]
    refreshed = _row_for(session, token)
    assert refreshed.expires_at > old_expiry + timedelta(days=19)
    assert refreshed.last_seen_at > _now() - timedelta(minutes=1)
    assert response.json()["expires_at"].startswith(refreshed.expires_at.isoformat()[:16])


def test_recent_session_does_not_slide_or_reissue_cookie(authed_client, session):
    token = authed_client.cookies.get("tc_session")
    before = _row_for(session, token).expires_at
    response = authed_client.get("/api/auth/me")
    assert response.status_code == 200
    assert "set-cookie" not in response.headers
    assert _row_for(session, token).expires_at == before


def test_cookie_is_secure_by_default(api_client, monkeypatch):
    monkeypatch.delenv("TRES_COMAS_COOKIE_SECURE")
    response = _login(api_client)
    assert response.status_code == 204
    assert re.search(r";\s*secure", response.headers["set-cookie"], re.I)


def test_cookie_not_secure_when_flag_is_zero(api_client):
    response = _login(api_client)
    assert not re.search(r";\s*secure", response.headers["set-cookie"], re.I)


# --- default deny ---------------------------------------------------------


def test_health_stays_public(api_client):
    assert api_client.get("/health").status_code == 200


def test_docs_and_openapi_are_off(api_client):
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert api_client.get(path).status_code == 404


def test_auth_default_deny_every_route(api_client):
    checked = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or route.path in PUBLIC_PATHS:
            continue
        path = re.sub(r"\{[^}]+\}", "1", route.path)
        method = sorted(route.methods)[0]
        response = api_client.request(method, path, json={})
        assert response.status_code == 401, f"{method} {route.path} is not protected"
        checked.append(route.path)
    assert "/api/auth/me" in checked  # the loop actually saw routes


def test_garbage_cookie_is_401(api_client):
    api_client.cookies.set("tc_session", "not-a-real-token")
    assert api_client.get("/api/auth/me").status_code == 401


# --- INV-3 ----------------------------------------------------------------


def test_inv3_password_hash_never_returned(api_client, monkeypatch):
    import os

    encoded = os.environ["TRES_COMAS_PASSWORD_HASH"]
    salt_part = encoded.split("$")[-2]
    responses = [
        _login(api_client, "wrong password attempt"),
        _login(api_client),
        api_client.get("/api/auth/me"),
        api_client.post("/api/auth/logout"),
        api_client.get("/api/auth/me"),
    ]
    monkeypatch.delenv("TRES_COMAS_PASSWORD_HASH")
    responses.append(_login(api_client))
    for r in responses:
        blob = r.text + "\n" + "\n".join(f"{k}: {v}" for k, v in r.headers.items())
        assert encoded not in blob
        assert salt_part not in blob
        assert TEST_PASSWORD not in blob
        assert "wrong password attempt" not in blob
