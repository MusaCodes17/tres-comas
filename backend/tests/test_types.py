"""DecimalText stores Decimal values exactly as TEXT (INV-9).

Uses a throwaway in-memory table, not the app models, so the type is tested
on its own.
"""

from decimal import Decimal

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, select, text
from sqlalchemy.exc import StatementError

from app.models.types import DecimalText


@pytest.fixture
def engine():
    eng = create_engine("sqlite://")
    meta = MetaData()
    table = Table(
        "t",
        meta,
        Column("id", Integer, primary_key=True),
        Column("v", DecimalText()),
    )
    meta.create_all(eng)
    eng.table = table
    yield eng
    eng.dispose()


def _roundtrip(engine, value):
    t = engine.table
    with engine.begin() as conn:
        conn.execute(t.insert().values(id=1, v=value))
        return conn.execute(select(t.c.v).where(t.c.id == 1)).scalar()


def _raw(engine):
    with engine.connect() as conn:
        return conn.execute(text("select v from t where id = 1")).scalar()


@pytest.mark.parametrize(
    "literal",
    [
        "0.3127",
        "1234567.12345678",
        "-42.5",
        "0.00000001",
        "1.2500",
        "12345678901234567890.1234567890",
    ],
)
def test_inv9_decimal_roundtrip_is_exact(engine, literal):
    stored = _roundtrip(engine, Decimal(literal))
    assert stored == Decimal(literal)
    assert format(stored, "f") == literal


def test_inv9_trailing_zeros_preserved_in_storage(engine):
    _roundtrip(engine, Decimal("1.2500"))
    assert _raw(engine) == "1.2500"


def test_inv9_exponent_input_stored_in_plain_notation(engine):
    _roundtrip(engine, Decimal("1E+3"))
    assert _raw(engine) == "1000"


def test_inv9_small_exponent_stored_in_plain_notation(engine):
    _roundtrip(engine, Decimal("1E-9"))
    assert _raw(engine) == "0.000000001"


def test_inv9_float_is_refused(engine):
    with pytest.raises(StatementError) as exc:
        _roundtrip(engine, 1.5)
    assert isinstance(exc.value.orig, TypeError)


def test_inv9_bool_is_refused(engine):
    with pytest.raises(StatementError) as exc:
        _roundtrip(engine, True)
    assert isinstance(exc.value.orig, TypeError)


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "abc"])
def test_inv9_non_finite_or_unparseable_string_is_refused(engine, bad):
    with pytest.raises(StatementError) as exc:
        _roundtrip(engine, bad)
    assert isinstance(exc.value.orig, ValueError)


def test_inv9_none_roundtrips_as_none(engine):
    assert _roundtrip(engine, None) is None


def test_inv9_int_roundtrips_as_decimal(engine):
    stored = _roundtrip(engine, 5)
    assert stored == Decimal("5")
    assert isinstance(stored, Decimal)
