"""Shared pytest fixtures.

DATABASE_URL is pointed at a throwaway SQLite file BEFORE ``app`` is imported,
so tests never touch the real data directory and never depend on a local .env.
"""

import os
import tempfile
from pathlib import Path

_TEST_DIR = tempfile.mkdtemp(prefix="tres-comas-tests-")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_TEST_DIR, "test.db")

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app.database import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.auth import hash_password, reset_login_throttle  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    """Return a TestClient bound to the app."""
    return TestClient(app)


_BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def session(tmp_path):
    """Yield a Session on a fresh migrated SQLite file, foreign keys on.

    ``session.get_bind()`` is the engine, so a test can open a second Session on it.
    """
    url = "sqlite:///" + str(tmp_path / "session.db")
    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    cfg.attributes["url"] = url
    command.upgrade(cfg, "head")
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    db = Session(engine)
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


TEST_PASSWORD = "correct horse battery"


@pytest.fixture
def api_client(session, monkeypatch) -> TestClient:
    """A TestClient wired to the migrated test database, with login configured.

    The password hash uses a cheap scrypt cost (n=2**10) so tests stay fast; the
    cookie is non-Secure so the client's jar sends it over plain http.
    """
    factory = sessionmaker(bind=session.get_bind(), autoflush=False)

    def _override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    monkeypatch.setenv("TRES_COMAS_PASSWORD_HASH", hash_password(TEST_PASSWORD, n=2**10))
    monkeypatch.setenv("TRES_COMAS_COOKIE_SECURE", "0")
    reset_login_throttle()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        reset_login_throttle()


@pytest.fixture
def authed_client(api_client) -> TestClient:
    """The api_client, already logged in."""
    response = api_client.post("/api/auth/login", json={"password": TEST_PASSWORD})
    assert response.status_code == 204
    return api_client
