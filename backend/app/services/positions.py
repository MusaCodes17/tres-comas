"""Position derivation: quantity, cost and realised gain from transactions.

Job: compute, per (account_id, security_id), what is held and what it cost,
purely from ledger transactions. Nothing here is stored.

Invariants upheld:
    INV-2  Positions are derived, never edited. There is no positions table; a
           position is always a fold over non-voided transactions.
    INV-9  Every quantity, cost and gain is a ``Decimal`` and every position
           carries its currency. No float is accepted or produced, and nothing
           is rounded or quantized: quantity, total cost and realised gain stay
           exact. Arithmetic runs in a local context with precision 34, so
           results do not depend on the global decimal context.

Method: weighted average cost (P-4) per (account_id, security_id), in the
transaction currency, which is the security's native currency. ``quantity`` on
a row is always positive (the type gives the direction); ``amount`` is a
non-negative cash magnitude. With q = quantity held, C = total cost and
G = realised gain, each type acts as follows:

    buy           q += quantity; C += amount (amount already includes fees).
    sell          removed = C * quantity / q (proportional removal, so selling
                  everything leaves C exactly 0); C -= removed; q -= quantity;
                  G += amount - removed (amount is net proceeds).
    transfer_in   like buy (amount is the cost basis carried in); no gain.
    transfer_out  like sell for q and C; G unchanged.
    split         q *= split_ratio; C unchanged (2 means 2-for-1, 0.1 means a
                  1-for-10 reverse split). ``quantity`` on a split is None.
    dividend, fee, deposit, withdrawal
                  no effect on positions, even when ``security_id`` is set.

Voided rows (``voided_at`` set) and rows with ``security_id`` None are ignored.
Rows are processed in (trade_date, id) order; a row whose id is None (not yet
flushed) sorts after every row of the same date, so a proposed row can be tested
before it is inserted.

Everything in this module only reads: nothing is flushed or committed.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Transaction

_PRECISION = 34
_ADDS = frozenset({"buy", "transfer_in"})
_REMOVES = frozenset({"sell", "transfer_out"})
_POSITION_TYPES = _ADDS | _REMOVES | {"split"}


@dataclass(frozen=True)
class Position:
    """Derived holding of one security in one account, in its native currency."""

    account_id: int
    security_id: int
    currency: str
    quantity: Decimal
    total_cost: Decimal
    realised_gain: Decimal

    @property
    def average_cost(self) -> Decimal | None:
        """Total cost per unit held, or None when nothing is held."""
        if self.quantity == 0:
            return None
        with localcontext() as ctx:
            ctx.prec = _PRECISION
            return self.total_cost / self.quantity


def _sort_key(row: Any) -> tuple[date, bool, int]:
    """Order by (trade_date, id); an unflushed row (id None) sorts last in its date."""
    return (row.trade_date, row.id is None, row.id if row.id is not None else 0)


def _label(row: Any) -> str:
    return (
        f"account_id={row.account_id} security_id={row.security_id} "
        f"trade_date={row.trade_date} transaction id={row.id}"
    )


def _decimal(row: Any, name: str, value: Any) -> Decimal:
    """Require a Decimal (INV-9: floats and strings never enter the arithmetic)."""
    if not isinstance(value, Decimal):
        raise TypeError(
            f"{name} must be a Decimal, got {type(value).__name__} ({_label(row)})"
        )
    return value


def derive(rows: Iterable[Any]) -> dict[tuple[int, int], Position]:
    """Derive positions from transactions. Pure: no database access.

    Args:
        rows: Transaction objects, or anything with the attributes id,
            account_id, security_id, type, quantity, amount, currency,
            split_ratio, trade_date and voided_at, in any order.

    Returns:
        Every position touched by a position-affecting row, keyed by
        (account_id, security_id), including positions now at quantity 0.

    Raises:
        ValueError: A sell or transfer_out exceeds the quantity held at that
            point ("would go negative"); a position's rows mix currencies; a
            buy, sell or transfer row has quantity None or <= 0, or amount < 0;
            a split has split_ratio None or <= 0.
        TypeError: A quantity, amount or split ratio is not a Decimal.
    """
    state: dict[tuple[int, int], dict[str, Any]] = {}
    live = [
        r
        for r in rows
        if r.voided_at is None and r.security_id is not None and r.type in _POSITION_TYPES
    ]
    with localcontext() as ctx:
        ctx.prec = _PRECISION
        for row in sorted(live, key=_sort_key):
            key = (row.account_id, row.security_id)
            pos = state.get(key)
            if pos is None:
                pos = state[key] = {
                    "currency": row.currency,
                    "q": Decimal("0"),
                    "c": Decimal("0"),
                    "g": Decimal("0"),
                }
            elif pos["currency"] != row.currency:
                raise ValueError(
                    f"mixed currency {pos['currency']} and {row.currency} in one "
                    f"position ({_label(row)})"
                )

            if row.type == "split":
                ratio = row.split_ratio
                if ratio is None or _decimal(row, "split_ratio", ratio) <= 0:
                    raise ValueError(f"split needs split_ratio > 0 ({_label(row)})")
                pos["q"] = pos["q"] * ratio
                continue

            if row.quantity is None or _decimal(row, "quantity", row.quantity) <= 0:
                raise ValueError(f"{row.type} needs quantity > 0 ({_label(row)})")
            quantity = row.quantity
            if _decimal(row, "amount", row.amount) < 0:
                raise ValueError(f"{row.type} needs amount >= 0 ({_label(row)})")
            amount = row.amount

            if row.type in _ADDS:
                pos["q"] = pos["q"] + quantity
                pos["c"] = pos["c"] + amount
                continue

            # sell / transfer_out
            if quantity > pos["q"]:
                raise ValueError(
                    f"{row.type} of {quantity} would go negative: only {pos['q']} "
                    f"held ({_label(row)})"
                )
            if quantity == pos["q"]:
                removed = pos["c"]
                pos["q"] = Decimal("0")
                pos["c"] = Decimal("0")
            else:
                removed = pos["c"] * quantity / pos["q"]
                pos["c"] = pos["c"] - removed
                pos["q"] = pos["q"] - quantity
            if row.type == "sell":
                pos["g"] = pos["g"] + (amount - removed)

    return {
        key: Position(
            account_id=key[0],
            security_id=key[1],
            currency=p["currency"],
            quantity=p["q"],
            total_cost=p["c"],
            realised_gain=p["g"],
        )
        for key, p in state.items()
    }


def _load(
    session: Session, *, account_id: int | None, as_of: date | None
) -> dict[tuple[int, int], Position]:
    stmt = (
        select(Transaction)
        .where(Transaction.voided_at.is_(None), Transaction.security_id.is_not(None))
        .order_by(Transaction.trade_date, Transaction.id)
    )
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    if as_of is not None:
        stmt = stmt.where(Transaction.trade_date <= as_of)
    return derive(session.scalars(stmt))


def get_positions(
    session: Session,
    *,
    account_id: int | None = None,
    as_of: date | None = None,
    include_closed: bool = False,
) -> list[Position]:
    """Positions derived from the ledger, sorted by (account_id, security_id).

    Read-only: never flushes or commits, so the caller owns the transaction.

    Args:
        session: Open session.
        account_id: Restrict to one account.
        as_of: Only transactions with trade_date on or before this date.
        include_closed: Also return positions now at quantity 0.

    Raises:
        ValueError: As for ``derive`` (oversell, mixed currency, bad row).
    """
    positions = _load(session, account_id=account_id, as_of=as_of)
    return [
        positions[key]
        for key in sorted(positions)
        if include_closed or positions[key].quantity != 0
    ]


def get_position(
    session: Session, *, account_id: int, security_id: int, as_of: date | None = None
) -> Position | None:
    """One position, or None if the pair never had a position-affecting row.

    A closed position (quantity 0) is returned, not None.

    Read-only: never flushes or commits.

    Raises:
        ValueError: As for ``derive``.
    """
    return _load(session, account_id=account_id, as_of=as_of).get((account_id, security_id))
