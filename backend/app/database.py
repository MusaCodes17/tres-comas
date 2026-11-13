"""Database engine, session factory and declarative base.

Job: own the single SQLAlchemy engine and session factory for the app, and
the declarative ``Base`` every ORM model inherits from. Nothing else.

Rationale: one engine per process keeps SQLite connections predictable under
the single-worker deployment (AGENTS.md §4.6). ``DATABASE_URL`` is read from
the environment so tests and production can point elsewhere without code edits.

Invariants: INV-9 (money is Decimal, never float). Money columns must use a
Decimal TypeDecorator stored as TEXT, never ``Float``; see
``docs/design_decisions.md`` D-15.
"""

import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "sqlite:///" + str(Path.home() / "tres-comas-data" / "tres_comas.db"),
)

_is_sqlite = DATABASE_URL.startswith("sqlite")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
        """SQLite ignores foreign keys unless enabled on every connection."""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    """Declarative base for all ORM models.

    Money columns must use a Decimal TypeDecorator (TEXT-backed), never
    ``Float`` (INV-9; design_decisions D-15).
    """


def get_db() -> Iterator[Session]:
    """Yield a database session for one request and close it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
