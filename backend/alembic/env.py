"""Alembic environment: wires migrations to the app's engine URL and metadata.

Job: tell Alembic which database to migrate (``app.database.DATABASE_URL``) and
which models to compare against (``app.database.Base.metadata``).

Rationale: SQLite cannot ALTER most constraints, so ``render_as_batch=True`` is
set in both offline and online modes (AGENTS.md §9).
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import DATABASE_URL, Base  # noqa: E402
import app.models  # noqa: E402,F401  (register models for autogenerate)

config = context.config
# An explicit URL (cfg.attributes["url"], used by tests) wins; else DATABASE_URL.
URL = config.attributes.get("url") or DATABASE_URL
config.set_main_option("sqlalchemy.url", URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live database connection."""
    context.configure(
        url=URL,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against a live database connection."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
