"""Tests for services/ledger.py: validation, never-negative, voiding, INV-2 and INV-9.

All data is synthetic. These tests go through the ledger; nothing here adds a
Transaction directly.
"""

from datetime import date, datetime
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, ImportBatch, Proposal, Security, Transaction
from app.services import ledger, positions


@pytest.fixture
def world(session):
    acct = Account(nickname="TFSA", type="tfsa", broker_label="Broker")
    acct2 = Account(nickname="RRSP", type="rrsp", broker_label="Broker")
    vgro = Security(ticker="VGRO", exchange="TSX", currency="CAD", kind="etf")
    aapl = Security(ticker="AAPL", exchange="NASDAQ", currency="USD", kind="stock")
    session.add_all([acct, acct2, vgro, aapl])
    session.commit()
    return SimpleNamespace(acct=acct.id, acct2=acct2.id, vgro=vgro.id, aapl=aapl.id)


def d(day, month=1):
    return date(2026, month, day)


def rec(session, w, type, **over):
    """Record a transaction with sensible defaults per type; override any field."""
    base = {
        "buy": dict(security_id=w.vgro, quantity="10", amount="100", price="10"),
        "sell": dict(security_id=w.vgro, quantity="5", amount="60"),
        "transfer_in": dict(security_id=w.vgro, quantity="5", amount="50"),
        "transfer_out": dict(security_id=w.vgro, quantity="5", amount="50"),
        "split": dict(security_id=w.vgro, split_ratio="2", amount="0"),
        "dividend": dict(amount="3"),
        "fee": dict(amount="1"),
        "deposit": dict(amount="1000"),
        "withdrawal": dict(amount="100"),
    }[type]
    kwargs = dict(
        account_id=w.acct, type=type, currency="CAD", trade_date=d(1), source="manual"
    )
    kwargs.update(base)
    kwargs.update(over)
    return ledger.record_transaction(session, **kwargs)


def count(session) -> int:
    return session.scalar(select(func.count()).select_from(Transaction))


# ------------------------------------------------------------------ recording


def test_all_nine_types_record_and_positions_reflect_them(session, world):
    w = world
    rec(session, w, "deposit")
    rec(session, w, "buy", trade_date=d(2))  # VGRO 10 @ cost 100
    rec(session, w, "sell", trade_date=d(3), quantity="4", amount="50")  # removes 40, gain 10
    rec(session, w, "split", trade_date=d(4))  # VGRO 12, cost 60
    rec(session, w, "dividend", trade_date=d(5), security_id=w.vgro)
    rec(session, w, "fee", trade_date=d(6))
    rec(session, w, "withdrawal", trade_date=d(7))
    rec(session, w, "transfer_in", trade_date=d(8), security_id=w.aapl, currency="USD",
        quantity="5", amount="500")
    rec(session, w, "transfer_out", trade_date=d(9), security_id=w.aapl, currency="USD",
        quantity="2", amount="200")
    assert count(session) == 9

    by_sec = {p.security_id: p for p in positions.get_positions(session, account_id=w.acct)}
    vgro, aapl = by_sec[w.vgro], by_sec[w.aapl]
    assert (vgro.quantity, vgro.total_cost, vgro.realised_gain) == (D("12"), D("60"), D("10"))
    assert vgro.currency == "CAD"
    assert (aapl.quantity, aapl.total_cost, aapl.currency) == (D("3"), D("300"), "USD")


def test_record_returns_flushed_row_with_exact_values(session, world):
    row = rec(session, world, "buy", quantity="0.3127", amount="12.50", price="39.98")
    assert row.id is not None
    assert row.quantity == D("0.3127") and row.voided_at is None and row.replaces_id is None


def test_fractional_quantity_round_trips_exactly_after_commit(session, world):
    row = rec(session, world, "buy", quantity="0.3127", amount="12.5000")
    tid = row.id
    session.commit()
    with Session(session.get_bind()) as other:
        got = other.get(Transaction, tid)
        assert got.quantity == D("0.3127")
        assert str(got.quantity) == "0.3127"
        assert str(got.amount) == "12.5000"


def test_int_and_decimal_inputs_accepted(session, world):
    row = rec(session, world, "buy", quantity=3, amount=D("30.5"))
    assert row.quantity == D("3") and row.amount == D("30.5")


# ------------------------------------------------------------------ INV-9


@pytest.mark.parametrize(
    "type, field",
    [
        ("buy", "amount"),
        ("buy", "quantity"),
        ("buy", "price"),
        ("split", "split_ratio"),
    ],
)
def test_inv9_ledger_rejects_float(session, world, type, field):
    with pytest.raises(TypeError):
        rec(session, world, type, **{field: 1.5})
    assert count(session) == 0


@pytest.mark.parametrize("field", ["amount", "quantity", "price"])
def test_inv9_ledger_rejects_bool(session, world, field):
    with pytest.raises(TypeError):
        rec(session, world, "buy", **{field: True})
    with pytest.raises(TypeError):
        rec(session, world, "split", split_ratio=True)
    assert count(session) == 0


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity", D("NaN"), D("Infinity")])
def test_inv9_ledger_rejects_non_finite(session, world, bad):
    with pytest.raises(ValueError):
        rec(session, world, "buy", amount=bad)
    with pytest.raises(ValueError):
        rec(session, world, "buy", quantity=bad)


def test_unparseable_string_is_value_error(session, world):
    with pytest.raises(ValueError):
        rec(session, world, "buy", amount="twelve")


def test_unsupported_decimal_type_is_type_error(session, world):
    with pytest.raises(TypeError):
        rec(session, world, "buy", amount=[1])


# ------------------------------------------------------------------ validation


def test_unknown_type_and_source_rejected(session, world):
    with pytest.raises(ValueError):
        ledger.record_transaction(
            session, account_id=world.acct, type="gift", amount="1", currency="CAD",
            trade_date=d(1), source="manual",
        )
    with pytest.raises(ValueError):
        rec(session, world, "buy", source="broker_api")


@pytest.mark.parametrize("cur", ["cad", "CA", "CADD", "", "C4D", None])
def test_bad_currency_rejected(session, world, cur):
    with pytest.raises(ValueError):
        rec(session, world, "deposit", currency=cur)


def test_trade_date_must_be_a_date_not_datetime(session, world):
    with pytest.raises(ValueError):
        rec(session, world, "deposit", trade_date=datetime(2026, 1, 1))
    with pytest.raises(ValueError):
        rec(session, world, "deposit", trade_date="2026-01-01")


@pytest.mark.parametrize(
    "type, over",
    [
        # buy / sell / transfers
        ("buy", dict(security_id=None)),
        ("buy", dict(quantity=None)),
        ("buy", dict(quantity="0")),
        ("buy", dict(quantity="-1")),
        ("buy", dict(amount="-1")),
        ("buy", dict(price="-1")),
        ("buy", dict(split_ratio="2")),
        ("buy", dict(amount=None)),
        ("sell", dict(security_id=None)),
        ("sell", dict(quantity="0")),
        ("sell", dict(amount="-0.01")),
        ("transfer_in", dict(security_id=None)),
        ("transfer_in", dict(quantity=None)),
        ("transfer_out", dict(quantity="-5")),
        ("transfer_out", dict(split_ratio="2")),
        # split
        ("split", dict(security_id=None)),
        ("split", dict(split_ratio=None)),
        ("split", dict(split_ratio="0")),
        ("split", dict(split_ratio="-2")),
        ("split", dict(quantity="1")),
        ("split", dict(price="1")),
        ("split", dict(amount="1")),
        # dividend / fee
        ("dividend", dict(amount="0")),
        ("dividend", dict(amount="-1")),
        ("dividend", dict(quantity="1")),
        ("dividend", dict(price="1")),
        ("dividend", dict(split_ratio="2")),
        ("fee", dict(amount="0")),
        ("fee", dict(quantity="1")),
        # deposit / withdrawal
        ("deposit", dict(amount="0")),
        ("deposit", dict(amount="-5")),
        ("deposit", dict(security_id=10)),
        ("deposit", dict(quantity="1")),
        ("withdrawal", dict(amount="0")),
        ("withdrawal", dict(price="1")),
        ("withdrawal", dict(split_ratio="1")),
    ],
)
def test_per_type_validation_rules(session, world, type, over):
    over = dict(over)
    if over.get("security_id") == 10:  # a real security id, to hit the "must be None" rule
        over["security_id"] = world.vgro
    # Seed shares so a sell/transfer_out is refused for the rule, not for lack of stock.
    rec(session, world, "buy", quantity="100", amount="1000", trade_date=d(1))
    before = count(session)
    with pytest.raises(ValueError):
        rec(session, world, type, trade_date=d(2), **over)
    assert count(session) == before


def test_optional_security_on_dividend_and_fee_and_zero_price_ok(session, world):
    rec(session, world, "dividend", security_id=world.vgro)
    rec(session, world, "fee", security_id=world.vgro)
    rec(session, world, "buy", price="0", amount="0")
    assert count(session) == 3


def test_unknown_account_and_security_lookup_error(session, world):
    with pytest.raises(LookupError):
        rec(session, world, "deposit", account_id=9999)
    with pytest.raises(LookupError):
        rec(session, world, "buy", security_id=9999)
    with pytest.raises(LookupError):
        rec(session, world, "dividend", security_id=9999)
    assert count(session) == 0


def test_currency_must_match_security_for_position_types(session, world):
    with pytest.raises(ValueError):
        rec(session, world, "buy", currency="USD")  # VGRO is CAD
    with pytest.raises(ValueError):
        rec(session, world, "split", currency="USD")
    # cash types are free to use any currency
    rec(session, world, "deposit", currency="USD")
    rec(session, world, "dividend", security_id=world.vgro, currency="USD")
    assert count(session) == 2


def test_import_source_pairing(session, world):
    batch = ImportBatch(account_id=world.acct, adapter="wealthsimple", file_kind="activity",
                        file_hash="a" * 64)
    session.add(batch)
    session.commit()

    row = rec(session, world, "deposit", source="import", import_batch_id=batch.id)
    assert row.import_batch_id == batch.id
    with pytest.raises(ValueError):
        rec(session, world, "deposit", source="import")
    with pytest.raises(ValueError):
        rec(session, world, "deposit", source="manual", import_batch_id=batch.id)
    with pytest.raises(ValueError):
        rec(session, world, "deposit", source="import", import_batch_id=batch.id, proposal_id=1)
    with pytest.raises(LookupError):
        rec(session, world, "deposit", source="import", import_batch_id=9999)


def test_proposal_source_pairing(session, world):
    prop = Proposal(payload="{}", origin="claude")
    session.add(prop)
    session.commit()

    row = rec(session, world, "deposit", source="proposal", proposal_id=prop.id)
    assert row.proposal_id == prop.id
    with pytest.raises(ValueError):
        rec(session, world, "deposit", source="proposal")
    with pytest.raises(ValueError):
        rec(session, world, "deposit", source="manual", proposal_id=prop.id)
    with pytest.raises(LookupError):
        rec(session, world, "deposit", source="proposal", proposal_id=9999)


def test_duplicate_natural_key_is_value_error(session, world):
    rec(session, world, "deposit", natural_key="k1")
    with pytest.raises(ValueError):
        rec(session, world, "deposit", natural_key="k1")
    assert count(session) == 1


# ------------------------------------------------------------------ never negative


def test_oversell_refused_and_nothing_added(session, world):
    rec(session, world, "buy", quantity="10", amount="100")
    before = count(session)
    with pytest.raises(ValueError, match="negative"):
        rec(session, world, "sell", quantity="10.0001", amount="100", trade_date=d(2))
    assert count(session) == before


def test_sell_with_no_position_refused(session, world):
    with pytest.raises(ValueError):
        rec(session, world, "sell")
    assert count(session) == 0


def test_back_dated_sell_that_breaks_a_later_sell_is_refused(session, world):
    rec(session, world, "buy", quantity="10", amount="100", trade_date=d(1, 1))
    rec(session, world, "sell", quantity="8", amount="90", trade_date=d(1, 3))
    before = count(session)
    with pytest.raises(ValueError, match="negative"):
        rec(session, world, "sell", quantity="5", amount="50", trade_date=d(1, 2))
    assert count(session) == before
    (pos,) = positions.get_positions(session)
    assert pos.quantity == D("2")


def test_sell_of_other_account_does_not_borrow_shares(session, world):
    rec(session, world, "buy", quantity="10", amount="100")
    with pytest.raises(ValueError):
        rec(session, world, "sell", account_id=world.acct2, quantity="1", amount="10")


# ------------------------------------------------------------------ voiding


def test_void_sets_voided_at_and_positions_ignore_it(session, world):
    buy = rec(session, world, "buy")
    out = ledger.void_transaction(session, transaction_id=buy.id)
    assert out is buy and buy.voided_at is not None and buy.voided_at.tzinfo is None
    assert positions.get_positions(session) == []
    assert count(session) == 1  # kept for history


def test_void_cash_row_ok(session, world):
    dep = rec(session, world, "deposit")
    ledger.void_transaction(session, transaction_id=dep.id)
    assert dep.voided_at is not None


def test_void_buy_that_a_later_sell_needs_is_refused(session, world):
    buy = rec(session, world, "buy", quantity="10", amount="100", trade_date=d(1))
    rec(session, world, "sell", quantity="4", amount="50", trade_date=d(2))
    with pytest.raises(ValueError, match="negative"):
        ledger.void_transaction(session, transaction_id=buy.id)
    session.refresh(buy)
    assert buy.voided_at is None


def test_void_twice_and_unknown_id(session, world):
    dep = rec(session, world, "deposit")
    ledger.void_transaction(session, transaction_id=dep.id)
    with pytest.raises(ValueError, match="already voided"):
        ledger.void_transaction(session, transaction_id=dep.id)
    with pytest.raises(LookupError):
        ledger.void_transaction(session, transaction_id=9999)


# ------------------------------------------------------------------ void and replace


def test_void_and_replace_corrects_the_numbers_and_keeps_history(session, world):
    old = rec(session, world, "buy", quantity="10", amount="100")
    new = ledger.void_and_replace(
        session, transaction_id=old.id, account_id=world.acct, type="buy", currency="CAD",
        trade_date=d(1), source="manual", security_id=world.vgro, quantity="8", amount="90",
    )
    assert new.id != old.id
    assert old.voided_at is not None and new.voided_at is None
    assert new.replaces_id == old.id and old.replaces_id is None
    assert count(session) == 2
    (pos,) = positions.get_positions(session)
    assert (pos.quantity, pos.total_cost) == (D("8"), D("90"))


def test_void_and_replace_can_move_to_another_security(session, world):
    old = rec(session, world, "buy")
    ledger.void_and_replace(
        session, transaction_id=old.id, account_id=world.acct, type="buy", currency="USD",
        trade_date=d(1), source="manual", security_id=world.aapl, quantity="3", amount="30",
    )
    (pos,) = positions.get_positions(session)
    assert pos.security_id == world.aapl and pos.quantity == D("3")


def test_void_and_replace_checks_the_old_pair_too(session, world):
    old = rec(session, world, "buy", quantity="10", amount="100", trade_date=d(1))
    rec(session, world, "sell", quantity="5", amount="60", trade_date=d(2))
    before = count(session)
    with pytest.raises(ValueError, match="negative"):
        ledger.void_and_replace(
            session, transaction_id=old.id, account_id=world.acct, type="buy", currency="USD",
            trade_date=d(1), source="manual", security_id=world.aapl, quantity="3", amount="30",
        )
    session.refresh(old)
    assert old.voided_at is None and count(session) == before


def test_void_and_replace_oversell_refused_atomically(session, world):
    rec(session, world, "buy", quantity="10", amount="100", trade_date=d(1))
    sell = rec(session, world, "sell", quantity="8", amount="90", trade_date=d(2))
    before = count(session)
    with pytest.raises(ValueError, match="negative"):
        ledger.void_and_replace(
            session, transaction_id=sell.id, account_id=world.acct, type="sell", currency="CAD",
            trade_date=d(2), source="manual", security_id=world.vgro, quantity="12", amount="130",
        )
    session.refresh(sell)
    assert sell.voided_at is None
    assert count(session) == before


def test_void_and_replace_invalid_fields_leave_old_row_live(session, world):
    old = rec(session, world, "deposit")
    with pytest.raises(ValueError):
        ledger.void_and_replace(
            session, transaction_id=old.id, account_id=world.acct, type="deposit",
            currency="CAD", trade_date=d(1), source="manual", amount="-1",
        )
    session.refresh(old)
    assert old.voided_at is None and count(session) == 1


def test_void_and_replace_errors(session, world):
    dep = rec(session, world, "deposit")
    fields = dict(account_id=world.acct, type="deposit", currency="CAD", trade_date=d(1),
                  source="manual", amount="5")
    with pytest.raises(LookupError):
        ledger.void_and_replace(session, transaction_id=9999, **fields)
    with pytest.raises(TypeError):  # replaces_id is not a public argument
        ledger.void_and_replace(session, transaction_id=dep.id, replaces_id=1, **fields)
    ledger.void_transaction(session, transaction_id=dep.id)
    with pytest.raises(ValueError, match="already voided"):
        ledger.void_and_replace(session, transaction_id=dep.id, **fields)


def test_record_transaction_has_no_replaces_id_parameter(session, world):
    with pytest.raises(TypeError):
        rec(session, world, "deposit", replaces_id=1)


# ------------------------------------------------------------------ commits


def test_record_transaction_does_not_commit(session, world):
    rec(session, world, "deposit")
    assert count(session) == 1
    session.rollback()
    assert count(session) == 0


def test_void_does_not_commit(session, world):
    dep = rec(session, world, "deposit")
    session.commit()
    ledger.void_transaction(session, transaction_id=dep.id)
    session.rollback()
    session.refresh(dep)
    assert dep.voided_at is None


# ------------------------------------------------------------------ INV-2


def test_inv2_ledger_is_sole_transaction_writer():
    app_dir = Path(__file__).resolve().parent.parent / "app"
    allowed_file = app_dir / "services" / "ledger.py"
    models_dir = app_dir / "models"
    needles = ("Transaction(", "insert(Transaction", "update(Transaction")
    scanned = 0
    offenders = []
    for path in sorted(app_dir.rglob("*.py")):
        if path == allowed_file or models_dir in path.parents:
            continue
        scanned += 1
        text = path.read_text()
        offenders += [f"{path.relative_to(app_dir)}: {n}" for n in needles if n in text]
    assert scanned > 0
    assert offenders == []
