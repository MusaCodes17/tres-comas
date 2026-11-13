"""Tests for services/positions.py: derivation rules, DB queries, F1 and INV-2.

All numbers are synthetic. Direct ``session.add`` of Transactions is allowed in
tests only; the ledger writer is T3b.
"""

from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from app.models import Account, Security, Transaction
from app.services.positions import Position, derive, get_position, get_positions

A, S = 1, 10


def tx(id, type, quantity=None, amount="0", day=1, *, account_id=A, security_id=S,
       currency="CAD", split_ratio=None, voided=False):
    """Build a transaction-shaped object (not persisted)."""
    return SimpleNamespace(
        id=id,
        account_id=account_id,
        security_id=security_id,
        type=type,
        quantity=None if quantity is None else D(quantity),
        amount=D(amount),
        currency=currency,
        split_ratio=None if split_ratio is None else D(split_ratio),
        trade_date=date(2026, 1, day),
        voided_at=object() if voided else None,
    )


def one(rows, key=(A, S)) -> Position:
    return derive(rows)[key]


# ---------------------------------------------------------------- pure derive


def test_two_buys_weighted_average():
    p = one([tx(1, "buy", "10", "100"), tx(2, "buy", "30", "420", day=2)])
    assert (p.quantity, p.total_cost, p.realised_gain) == (D("40"), D("520"), D("0"))
    assert p.average_cost == D("13")
    assert p.currency == "CAD"


def test_partial_sell_realised_gain_and_remaining_cost():
    p = one([tx(1, "buy", "10", "100"), tx(2, "buy", "30", "420", day=2),
             tx(3, "sell", "10", "200", day=3)])
    # removed cost = 520 * 10 / 40 = 130
    assert p.quantity == D("30")
    assert p.total_cost == D("390")
    assert p.realised_gain == D("70")
    assert p.average_cost == D("13")


def test_sell_everything_leaves_exact_zero_cost():
    p = one([tx(1, "buy", "3", "10"), tx(2, "buy", "3", "10", day=2),
             tx(3, "buy", "1", "0.01", day=3), tx(4, "sell", "7", "50", day=4)])
    assert p.quantity == D("0")
    assert p.total_cost == D("0")
    assert str(p.total_cost) == "0"
    assert p.realised_gain == D("50") - D("20.01")
    assert p.average_cost is None


def test_sell_with_inexact_proportion_still_closes_to_zero():
    p = one([tx(1, "buy", "3", "10"), tx(2, "sell", "1", "5", day=2),
             tx(3, "sell", "2", "5", day=3)])
    assert p.quantity == 0
    assert p.total_cost == D("0")


def test_two_for_one_split():
    p = one([tx(1, "buy", "10", "100"), tx(2, "split", day=2, split_ratio="2")])
    assert p.quantity == D("20")
    assert p.total_cost == D("100")
    assert p.average_cost == D("5")


def test_one_for_ten_reverse_split():
    p = one([tx(1, "buy", "100", "100"), tx(2, "split", day=2, split_ratio="0.1")])
    assert p.quantity == D("10.0")
    assert p.total_cost == D("100")
    assert p.average_cost == D("10")


def test_fractional_shares_round_trip_exactly():
    p = one([tx(1, "buy", "0.3127", "10.55"), tx(2, "buy", "1.2500", "40", day=2)])
    assert p.quantity == D("1.5627")
    assert f"{p.quantity:.4f}" == "1.5627"
    assert p.total_cost == D("50.55")


def test_voided_rows_ignored():
    p = one([tx(1, "buy", "10", "100"), tx(2, "buy", "99", "999", day=2, voided=True)])
    assert p.quantity == D("10")
    assert p.total_cost == D("100")


def test_only_voided_rows_yield_no_position():
    assert derive([tx(1, "buy", "10", "100", voided=True)]) == {}


def test_void_and_replace_pair_gives_replaced_numbers():
    rows = [
        tx(1, "buy", "10", "100", voided=True),  # typo
        tx(2, "buy", "10", "110"),  # replacement
    ]
    p = one(rows)
    assert (p.quantity, p.total_cost) == (D("10"), D("110"))


def test_same_day_sell_before_buy_by_id_raises():
    rows = [tx(1, "sell", "5", "50", day=5), tx(2, "buy", "10", "100", day=5)]
    with pytest.raises(ValueError, match="would go negative"):
        derive(rows)


def test_same_day_buy_then_sell_by_id_succeeds():
    rows = [tx(2, "sell", "5", "60", day=5), tx(1, "buy", "10", "100", day=5)]
    p = one(rows)  # input order is irrelevant; ids decide
    assert p.quantity == D("5")
    assert p.realised_gain == D("10")


def test_earlier_date_wins_over_lower_id():
    rows = [tx(1, "sell", "5", "50", day=6), tx(2, "buy", "10", "100", day=5)]
    assert one(rows).quantity == D("5")


def test_unflushed_row_sorts_last_within_its_date():
    rows = [tx(None, "sell", "10", "150", day=5), tx(7, "buy", "10", "100", day=5)]
    p = one(rows)
    assert p.quantity == D("0")
    assert p.realised_gain == D("50")


def test_unflushed_sell_proposed_with_nothing_held_raises_naming_context():
    with pytest.raises(ValueError, match=r"would go negative.*account_id=1.*security_id=10"):
        derive([tx(None, "sell", "1", "5")])


def test_oversell_raises():
    with pytest.raises(ValueError, match="would go negative"):
        derive([tx(1, "buy", "1", "10"), tx(2, "sell", "1.0001", "10", day=2)])


def test_transfer_out_oversell_raises():
    with pytest.raises(ValueError, match="would go negative"):
        derive([tx(1, "buy", "1", "10"), tx(2, "transfer_out", "2", "20", day=2)])


def test_mixed_currency_raises():
    with pytest.raises(ValueError, match="mixed currency"):
        derive([tx(1, "buy", "1", "10"), tx(2, "buy", "1", "10", day=2, currency="USD")])


def test_different_positions_may_use_different_currencies():
    out = derive([tx(1, "buy", "1", "10"),
                  tx(2, "buy", "1", "10", security_id=11, currency="USD")])
    assert out[(A, S)].currency == "CAD"
    assert out[(A, 11)].currency == "USD"


def test_transfer_in_carries_cost_without_gain():
    p = one([tx(1, "transfer_in", "10", "100")])
    assert (p.quantity, p.total_cost, p.realised_gain) == (D("10"), D("100"), D("0"))


def test_transfer_out_removes_cost_without_gain():
    p = one([tx(1, "buy", "10", "100"), tx(2, "transfer_out", "4", "999", day=2)])
    assert (p.quantity, p.total_cost, p.realised_gain) == (D("6"), D("60"), D("0"))


def test_cash_types_and_null_security_ignored():
    rows = [
        tx(1, "buy", "10", "100"),
        tx(2, "dividend", amount="5", day=2),
        tx(3, "fee", amount="1", day=2),
        tx(4, "deposit", amount="500", day=2, security_id=None),
        tx(5, "withdrawal", amount="50", day=2, security_id=None),
        tx(6, "buy", "5", "50", day=2, security_id=None),
    ]
    out = derive(rows)
    assert list(out) == [(A, S)]
    p = out[(A, S)]
    assert (p.quantity, p.total_cost, p.realised_gain) == (D("10"), D("100"), D("0"))


def test_cash_row_with_security_does_not_create_position():
    assert derive([tx(1, "dividend", amount="5")]) == {}


def test_closed_position_is_still_returned():
    out = derive([tx(1, "buy", "1", "10"), tx(2, "sell", "1", "12", day=2)])
    assert out[(A, S)].quantity == 0


def test_positions_are_per_account_and_security():
    out = derive([tx(1, "buy", "1", "10"), tx(2, "buy", "2", "20", account_id=2),
                  tx(3, "buy", "3", "30", security_id=11)])
    assert {k: v.quantity for k, v in out.items()} == {
        (1, 10): D("1"), (2, 10): D("2"), (1, 11): D("3")}


@pytest.mark.parametrize(
    "row",
    [
        tx(1, "buy", None, "10"),
        tx(1, "buy", "0", "10"),
        tx(1, "buy", "-1", "10"),
        tx(1, "buy", "1", "-10"),
        tx(1, "transfer_in", None, "10"),
        tx(1, "split"),  # ratio None
        tx(1, "split", split_ratio="0"),
        tx(1, "split", split_ratio="-2"),
    ],
)
def test_bad_rows_raise(row):
    with pytest.raises(ValueError):
        derive([row])


def test_sell_with_bad_quantity_or_amount_raises():
    base = tx(1, "buy", "5", "50")
    with pytest.raises(ValueError):
        derive([base, tx(2, "sell", "0", "1", day=2)])
    with pytest.raises(ValueError):
        derive([base, tx(2, "sell", "1", "-1", day=2)])


def test_non_decimal_quantity_is_rejected():
    bad = tx(1, "buy", "1", "10")
    bad.quantity = "1"
    with pytest.raises(TypeError):
        derive([bad])


def test_voided_bad_row_is_ignored():
    assert derive([tx(1, "buy", None, "10", voided=True)]) == {}


def test_precision_is_independent_of_global_context():
    import decimal

    saved = decimal.getcontext().prec
    decimal.getcontext().prec = 3
    try:
        p = one([tx(1, "buy", "0.3127", "10.5512345678")])
        assert p.total_cost == D("10.5512345678")
        assert p.quantity == D("0.3127")
        assert len(str(p.average_cost)) > 20  # computed at prec 34, not the global 3
    finally:
        decimal.getcontext().prec = saved


# ------------------------------------------------------------------ DB tests


def _seed(session: Session):
    acct = Account(nickname="tfsa-main", type="tfsa")
    other = Account(nickname="rrsp-main", type="rrsp")
    sec = Security(ticker="VGRO", exchange="TSX", currency="CAD", kind="etf")
    sec2 = Security(ticker="AAPL", exchange="NASDAQ", currency="USD", kind="stock")
    session.add_all([acct, other, sec, sec2])
    session.flush()
    return acct, other, sec, sec2


def _add(session, account, security, type, quantity, amount, day, month=1, currency="CAD"):
    t = Transaction(
        account_id=account.id,
        security_id=security.id if security else None,
        type=type,
        quantity=None if quantity is None else D(quantity),
        amount=D(amount),
        currency=currency,
        trade_date=date(2026, month, day),
        source="manual",
    )
    session.add(t)
    session.flush()
    return t


def test_get_positions_basic_and_sorted(session):
    acct, other, sec, sec2 = _seed(session)
    _add(session, other, sec, "buy", "2", "20", 1)
    _add(session, acct, sec2, "buy", "1.5", "300", 1, currency="USD")
    _add(session, acct, sec, "buy", "0.3127", "10", 1)
    got = get_positions(session)
    assert [(p.account_id, p.security_id) for p in got] == sorted(
        (p.account_id, p.security_id) for p in got)
    assert len(got) == 3
    p = get_position(session, account_id=acct.id, security_id=sec.id)
    assert p.quantity == D("0.3127")


def test_as_of_excludes_later_rows(session):
    acct, _, sec, _ = _seed(session)
    _add(session, acct, sec, "buy", "10", "100", 1)
    _add(session, acct, sec, "buy", "5", "60", 1, month=2)
    assert get_position(session, account_id=acct.id, security_id=sec.id,
                        as_of=date(2026, 1, 31)).quantity == D("10")
    assert get_position(session, account_id=acct.id, security_id=sec.id,
                        as_of=date(2026, 2, 1)).quantity == D("15")
    assert get_positions(session, as_of=date(2025, 12, 31)) == []
    assert get_position(session, account_id=acct.id, security_id=sec.id,
                        as_of=date(2025, 12, 31)) is None


def test_account_filter(session):
    acct, other, sec, _ = _seed(session)
    _add(session, acct, sec, "buy", "10", "100", 1)
    _add(session, other, sec, "buy", "3", "30", 1)
    got = get_positions(session, account_id=other.id)
    assert [(p.account_id, p.quantity) for p in got] == [(other.id, D("3"))]


def test_include_closed(session):
    acct, _, sec, sec2 = _seed(session)
    _add(session, acct, sec, "buy", "10", "100", 1)
    _add(session, acct, sec, "sell", "10", "120", 2)
    _add(session, acct, sec2, "buy", "1", "5", 1, currency="USD")
    assert [p.security_id for p in get_positions(session)] == [sec2.id]
    closed = get_positions(session, include_closed=True)
    assert [p.security_id for p in closed] == sorted([sec.id, sec2.id])
    p = get_position(session, account_id=acct.id, security_id=sec.id)
    assert p is not None and p.quantity == 0 and p.realised_gain == D("20")


def test_get_position_unknown_pair_is_none(session):
    acct, _, sec, sec2 = _seed(session)
    _add(session, acct, sec, "buy", "10", "100", 1)
    assert get_position(session, account_id=acct.id, security_id=sec2.id) is None
    assert get_position(session, account_id=999, security_id=sec.id) is None


def test_cash_rows_and_voided_rows_ignored_in_db(session):
    acct, _, sec, _ = _seed(session)
    _add(session, acct, None, "deposit", None, "1000", 1)
    _add(session, acct, sec, "dividend", None, "3", 2)
    _add(session, acct, sec, "buy", "10", "100", 2)
    bad = _add(session, acct, sec, "buy", "50", "500", 3)
    bad.voided_at = date(2026, 1, 4)
    session.flush()
    p = get_position(session, account_id=acct.id, security_id=sec.id)
    assert (p.quantity, p.total_cost) == (D("10"), D("100"))


def test_get_positions_does_not_write(session):
    acct, _, sec, _ = _seed(session)
    _add(session, acct, sec, "buy", "10", "100", 1)
    get_positions(session)
    assert not session.new and not session.dirty


def test_f1_nine_tfsa_positions_to_four_decimals(session):
    acct = Account(nickname="tfsa-main", type="tfsa", broker_label="broker")
    session.add(acct)
    specs = [
        ("AAPL", "NASDAQ", "USD", "stock"),
        ("GOOG", "NASDAQ", "USD", "stock"),
        ("MDA", "TSX", "CAD", "stock"),
        ("NOK", "NYSE", "USD", "stock"),
        ("NVDA", "NASDAQ", "USD", "stock"),
        ("RKLB", "NASDAQ", "USD", "stock"),
        ("VGRO", "TSX", "CAD", "etf"),
        ("XEQT", "TSX", "CAD", "etf"),
        ("XGRO", "TSX", "CAD", "etf"),
    ]
    secs = {}
    for ticker, exch, cur, kind in specs:
        s = Security(ticker=ticker, exchange=exch, currency=cur, kind=kind)
        session.add(s)
        secs[ticker] = s
    session.flush()

    # ticker: (currency, [(type, quantity, amount, month, day)], expected)
    plan = {
        "AAPL": ("USD", [("buy", "1.2500", "250.00", 1, 5), ("buy", "0.3127", "70.10", 2, 3)],
                 "1.5627"),
        "GOOG": ("USD", [("buy", "2.0000", "340.00", 1, 6), ("buy", "0.5000", "90.00", 3, 1),
                         ("sell", "0.7500", "140.00", 4, 1)], "1.7500"),
        "MDA": ("CAD", [("buy", "10.0000", "300.00", 1, 7), ("buy", "4.1234", "130.00", 2, 7)],
                "14.1234"),
        "NOK": ("USD", [("buy", "100.0000", "450.00", 1, 8), ("buy", "25.5000", "120.00", 2, 8),
                        ("buy", "0.0001", "0.00", 3, 8)], "125.5001"),
        "NVDA": ("USD", [("buy", "3.3333", "400.00", 1, 9), ("buy", "1.1111", "150.00", 2, 9)],
                 "4.4444"),
        "RKLB": ("USD", [("buy", "20.0000", "200.00", 1, 10), ("buy", "7.7777", "100.00", 2, 10)],
                 "27.7777"),
        "VGRO": ("CAD", [("buy", "12.3456", "400.00", 1, 11), ("buy", "0.3127", "10.50", 2, 11),
                         ("buy", "5.0000", "170.00", 3, 11)], "17.6583"),
        "XEQT": ("CAD", [("buy", "8.0000", "260.00", 1, 12), ("buy", "2.2500", "75.00", 2, 12)],
                 "10.2500"),
        "XGRO": ("CAD", [("buy", "6.5000", "190.00", 1, 13), ("buy", "1.0000", "29.00", 2, 13),
                         ("sell", "0.2500", "8.00", 3, 13)], "7.2500"),
    }
    for ticker, (cur, rows, _) in plan.items():
        for type_, q, amt, m, d in rows:
            _add(session, acct, secs[ticker], type_, q, amt, d, month=m, currency=cur)

    got = {p.security_id: p for p in get_positions(session, account_id=acct.id)}
    assert len(got) == 9
    for ticker, (cur, _, expected) in plan.items():
        p = got[secs[ticker].id]
        assert f"{p.quantity:.4f}" == expected, ticker
        assert p.currency == cur


def test_inv2_positions_rebuild_from_transactions(session):
    acct, other, sec, sec2 = _seed(session)
    _add(session, acct, sec, "buy", "10.3127", "100.10", 1)
    _add(session, acct, sec, "sell", "3.0001", "40.00", 2)
    _add(session, acct, sec, "dividend", None, "2.00", 2)
    _add(session, acct, sec2, "buy", "1.5", "300", 1, currency="USD")
    _add(session, other, sec, "buy", "2", "20", 3)
    session.commit()

    first = get_positions(session, include_closed=True)
    engine = session.get_bind()
    with Session(engine) as fresh:
        again = get_positions(fresh, include_closed=True)
        rows = fresh.query(Transaction).all()
        rebuilt = sorted(derive(rows).values(), key=lambda p: (p.account_id, p.security_id))
    assert first == again == rebuilt
    assert len(first) == 3
