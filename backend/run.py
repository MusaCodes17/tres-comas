"""Local development entry point.

Job: make sure the SQLite data directory exists, apply migrations to head, then
serve the app on localhost.

Port 8001 because Anton uses 8000 on the same box. One worker because the
price/FX scheduler is in-process (AGENTS.md §4.6).
"""

import os
from pathlib import Path

import uvicorn
from alembic.config import main as alembic_main

from app.database import DATABASE_URL

BACKEND_DIR = Path(__file__).resolve().parent


def _ensure_sqlite_parent_dir() -> None:
    """Create the parent directory of a sqlite DATABASE_URL if it is missing."""
    prefix = "sqlite:///"
    if DATABASE_URL.startswith(prefix):
        Path(DATABASE_URL[len(prefix):]).parent.mkdir(parents=True, exist_ok=True)


def main() -> None:
    """Prepare the data directory, run migrations, then start uvicorn."""
    _ensure_sqlite_parent_dir()

    previous_cwd = Path.cwd()
    os.chdir(BACKEND_DIR)
    try:
        alembic_main(argv=["upgrade", "head"])
    finally:
        os.chdir(previous_cwd)

    uvicorn.run("app.main:app", host="127.0.0.1", port=8001, workers=1)


if __name__ == "__main__":
    main()
