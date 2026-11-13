"""Schema tests: the ten tables, invariants INV-2/8/9, and DB-level constraints.

Each test migrates a fresh temp SQLite file to head, then talks to it through an
engine with foreign keys switched on (as app.database does).
"""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Float, Numeric, create_engine, event, inspect, text
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Account, Connection, DecimalText, FxRate, Transaction

BACKEND_DIR = Path(__file__).resolve().parent.parent

TABLES = {
    "accounts",
    "securities",
    "import_batches",
    "proposals",
    "transactions",
    "prices",
    "fx_rates",
    "etf_constituents",
    "connections",
    "outbound_logs",
}


def _cfg(url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.attributes["url"] = url
    return cfg


@pytest.fixture
def db(tmp_path):
    url = "sqlite:///" + str(tmp_path / "schema.db")
    cfg = _cfg(url)
    command.upgrade(cfg, "head")
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_connection, record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    engine.cfg = cfg
    yield engine
    engine.dispose()


def _account(session) -> Account:
    acct = Account(nickname="tfsa-main", type="tfsa")
    session.add(acct)
    session.flush()
    return acct


def _tx(account_id: int, **kw) -> Transaction:
    base = dict(
        account_id=account_id,
        type="deposit",
        amount=Decimal("100.00"),
        currency="CAD",
        trade_date=date(2026, 1, 2),
        source="manual",
    )
    base.update(kw)
    return Transaction(**base)


def _table_names(engine) -> set[str]:
    return set(inspect(engine).get_table_names()) - {"alembic_version"}


def test_upgrade_creates_the_ten_tables(db):
    # auth_sessions (T4, migration 0002) is the one non-ledger table.
    assert _table_names(db) == TABLES | {"auth_sessions"}


def test_migration_matches_models(db):
    with db.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": True})
        assert compare_metadata(ctx, Base.metadata) == []


def test_inv9_no_float_or_numeric_columns():
    decimal_names = {"quantity", "price", "amount", "close", "rate", "weight", "split_ratio"}
    for table in Base.metadata.tables.values():
        for col in table.columns:
            assert not isinstance(col.type, (Float, Numeric)), f"{table.name}.{col.name}"
            assert "REAL" not in str(col.type).upper(), f"{table.name}.{col.name}"
            if col.name in decimal_names:
                assert isinstance(col.type, DecimalText), f"{table.name}.{col.name}"


def test_inv9_money_tables_have_currency():
    for name in ("transactions", "prices"):
        col = Base.metadata.tables[name].columns["currency"]
        assert not col.nullable


def test_inv8_accounts_have_no_account_number_column():
    for col in Base.metadata.tables["accounts"].columns:
        assert "number" not in col.name and "acct_no" not in col.name


def test_inv2_no_positions_table(db):
    assert not [t for t in _table_names(db) if "position" in t]
    assert not [t for t in Base.metadata.tables if "position" in t]


def test_inv2_transaction_delete_is_refused(db):
    with Session(db) as s:
        a = _account(s)
        s.add(_tx(a.id))
        s.commit()
    with pytest.raises(DatabaseError, match="append-only"):
        with db.begin() as conn:
            conn.execute(text("DELETE FROM transactions"))


def test_inv2_transaction_amount_update_is_refused(db):
    with Session(db) as s:
        a = _account(s)
        s.add(_tx(a.id))
        s.commit()
    with pytest.raises(DatabaseError, match="append-only"):
        with db.begin() as conn:
            conn.execute(text("UPDATE transactions SET amount = '999'"))


def test_inv2_voiding_once_is_allowed_twice_is_refused(db):
    with Session(db) as s:
        a = _account(s)
        s.add(_tx(a.id))
        s.commit()
    with db.begin() as conn:
        conn.execute(text("UPDATE transactions SET voided_at = '2026-02-01 00:00:00'"))
    with pytest.raises(DatabaseError, match="append-only"):
        with db.begin() as conn:
            conn.execute(text("UPDATE transactions SET voided_at = '2026-03-01 00:00:00'"))


def test_inv2_void_and_replace_pair(db):
    with Session(db) as s:
        a = _account(s)
        old = _tx(a.id)
        s.add(old)
        s.flush()
        old_id = old.id
        s.commit()
    with db.begin() as conn:
        conn.execute(text("UPDATE transactions SET voided_at = '2026-02-01 00:00:00'"))
    with Session(db) as s:
        s.add(_tx(1, amount=Decimal("110.00"), replaces_id=old_id))
        s.commit()
        assert s.query(Transaction).count() == 2


def test_decimal_roundtrip_through_transactions(db):
    with Session(db) as s:
        a = _account(s)
        s.add(_tx(a.id, amount=Decimal("0.3127")))
        s.commit()
    with Session(db) as s:
        assert s.query(Transaction).one().amount == Decimal("0.3127")


def test_fk_enforced(db):
    with Session(db) as s:
        s.add(_tx(9999))
        with pytest.raises(IntegrityError):
            s.commit()


def test_currency_and_pair_checks(db):
    for bad in ("cad", "CA"):
        with Session(db) as s:
            a = _account(s)
            s.add(_tx(a.id, currency=bad))
            with pytest.raises(IntegrityError):
                s.commit()
    with Session(db) as s:
        s.add(FxRate(pair="USDCAD", rate_date=date(2026, 1, 2), rate=Decimal("1.39"), provider="boc"))
        with pytest.raises(IntegrityError):
            s.commit()
    with Session(db) as s:
        s.add(FxRate(pair="USD_CAD", rate_date=date(2026, 1, 2), rate=Decimal("1.39"), provider="boc"))
        s.commit()


def test_connections_default_disabled(db):
    with Session(db) as s:
        s.add(Connection(name="prices", kind="market_data", direction="outbound", scope="{}"))
        s.commit()
    with Session(db) as s:
        assert s.query(Connection).one().enabled is False


def test_connection_kind_direction_check(db):
    with Session(db) as s:
        s.add(Connection(name="bad", kind="market_data", direction="inbound", scope="{}"))
        with pytest.raises(IntegrityError):
            s.commit()


def test_downgrade_drops_everything(db):
    command.downgrade(db.cfg, "base")
    assert _table_names(db) == set()
    with db.connect() as conn:
        triggers = conn.execute(text("SELECT name FROM sqlite_master WHERE type='trigger'")).all()
    assert triggers == []
