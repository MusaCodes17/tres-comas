"""Shared pytest fixtures.

DATABASE_URL is pointed at a throwaway SQLite file BEFORE ``app`` is imported,
so tests never touch the real data directory and never depend on a local .env.
"""

import os
import tempfile

_TEST_DIR = tempfile.mkdtemp(prefix="tres-comas-tests-")
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_TEST_DIR, "test.db")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    """Return a TestClient bound to the app."""
    return TestClient(app)
