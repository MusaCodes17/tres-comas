"""The ledger write path: the only code that creates, voids or corrects a transaction.

Job: validate a proposed ledger entry, refuse any change that would make a
position go negative on any date, and write it. Manual entry (T4), CSV import
(T5) and confirmed proposals (T11) all call ``record_transaction``; there is no
parallel path.

Invariants upheld:
    INV-2  Transactions are the truth and are append-only. The only UPDATE this
           module ever makes is setting ``voided_at`` on a live row (the database
           triggers allow exactly that). A correction is ``void_and_replace``:
           void the old row, add a new row whose ``replaces_id`` points back.
           Nothing here writes a position; positions are derived by
           ``services.positions``.
    INV-6  External clients cannot write the ledger. ``source="proposal"`` is
           accepted only together with the id of the ``Proposal`` row that Musa
           confirmed in the app, and the caller of this module is that app code.
    INV-9  ``amount``, ``quantity``, ``price`` and ``split_ratio`` are exact
           ``Decimal`` values. Floats and bools are refused with ``TypeError``;
           strings and ints are converted exactly; nothing is quantized. Every
           row carries an ISO 4217 currency.

Callers own the commit. Every function here flushes and never commits, so an
import batch or a proposal confirmation stays atomic. All checks run in Python
before any write, so a refused call changes nothing.

Never-negative rule: before a row is added, voided or replaced, the affected
(account_id, security_id) histories are re-derived with the change applied. If
that derivation fails (for example a back-dated sell that leaves a later sell
short of shares) the call raises ``ValueError`` and nothing is written.

Type semantics (quantity is always positive and the type gives the direction;
amount is a non-negative cash magnitude, in the row's currency):
    buy, sell, transfer_in, transfer_out
        security_id and quantity > 0 required; amount >= 0; price optional (>= 0).
    split
        security_id and split_ratio > 0 required (new shares per old share);
        quantity and price None; amount 0.
    dividend, fee
        amount > 0; security_id optional; no quantity, price or split_ratio.
    deposit, withdrawal
        amount > 0; no security_id, quantity, price or split_ratio.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, ImportBatch, Proposal, Security, Transaction
from app.services import positions

TRANSACTION_TYPES = (
    "buy",
    "sell",
    "dividend",
    "deposit",
    "withdrawal",
    "fee",
    "split",
    "transfer_in",
    "transfer_out",
)
SOURCES = ("manual", "import", "proposal")

_QUANTITY_TYPES = frozenset({"buy", "sell", "transfer_in", "transfer_out"})
_POSITION_TYPES = _QUANTITY_TYPES | {"split"}
_CASH_TYPES = frozenset({"dividend", "fee", "deposit", "withdrawal"})
_CURRENCY_RE = re.compile(r"[A-Z]{3}")

_ZERO = Decimal("0")


def _to_decimal(name: str, value: object) -> Decimal:
    """Convert a Decimal, str or int to an exact finite Decimal (INV-9).

    Raises:
        TypeError: ``value`` is a float, a bool, or any other unsupported type.
        ValueError: ``value`` is an unparseable string, NaN or infinite.
    """
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError(
            f"{name} must be a Decimal, str or int, not {type(value).__name__} (INV-9)"
        )
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, (str, int)):
        try:
            result = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"{name} is not a number: {value!r}") from exc
    else:
        raise TypeError(
            f"{name} must be a Decimal, str or int, not {type(value).__name__} (INV-9)"
        )
    if not result.is_finite():
        raise ValueError(f"{name} must be finite, got {value!r}")
    return result


def _optional_decimal(name: str, value: object) -> Decimal | None:
    return None if value is None else _to_decimal(name, value)


def _build(
    session: Session,
    *,
    account_id: int,
    type: str,
    amount: object,
    currency: str,
    trade_date: date,
    source: str,
    security_id: int | None = None,
    quantity: object = None,
    price: object = None,
    split_ratio: object = None,
    import_batch_id: int | None = None,
    proposal_id: int | None = None,
    natural_key: str | None = None,
    note: str | None = None,
) -> Transaction:
    """Validate the fields and return an UNSAVED Transaction (not added to the session).

    Does not flush or commit. ``replaces_id`` is deliberately not a parameter:
    only ``void_and_replace`` sets it.

    Raises:
        TypeError: A decimal field is a float, bool or unsupported type.
        ValueError: Any field violates the rules in the module docstring, or
            ``natural_key`` is already used by another transaction.
        LookupError: The account, security, import batch or proposal does not exist.
    """
    if type not in TRANSACTION_TYPES:
        raise ValueError(f"type must be one of {TRANSACTION_TYPES}, got {type!r}")
    if source not in SOURCES:
        raise ValueError(f"source must be one of {SOURCES}, got {source!r}")
    if not isinstance(currency, str) or not _CURRENCY_RE.fullmatch(currency):
        raise ValueError(f"currency must be three uppercase letters (ISO 4217), got {currency!r}")
    if not isinstance(trade_date, date) or isinstance(trade_date, datetime):
        raise ValueError("trade_date must be a datetime.date, not a datetime")

    if amount is None:
        raise ValueError("amount is required")
    amount_d = _to_decimal("amount", amount)
    quantity_d = _optional_decimal("quantity", quantity)
    price_d = _optional_decimal("price", price)
    ratio_d = _optional_decimal("split_ratio", split_ratio)

    if type in _QUANTITY_TYPES:
        if security_id is None:
            raise ValueError(f"{type} requires security_id")
        if quantity_d is None or quantity_d <= _ZERO:
            raise ValueError(f"{type} requires quantity > 0")
        if amount_d < _ZERO:
            raise ValueError(f"{type} requires amount >= 0")
        if price_d is not None and price_d < _ZERO:
            raise ValueError(f"{type} requires price >= 0 when given")
        if ratio_d is not None:
            raise ValueError(f"{type} must not have split_ratio")
    elif type == "split":
        if security_id is None:
            raise ValueError("split requires security_id")
        if ratio_d is None or ratio_d <= _ZERO:
            raise ValueError("split requires split_ratio > 0")
        if quantity_d is not None or price_d is not None:
            raise ValueError("split must not have quantity or price")
        if amount_d != _ZERO:
            raise ValueError("split requires amount == 0")
    else:
        if amount_d <= _ZERO:
            raise ValueError(f"{type} requires amount > 0")
        if type in ("deposit", "withdrawal") and security_id is not None:
            raise ValueError(f"{type} must not have security_id")
        if quantity_d is not None or price_d is not None or ratio_d is not None:
            raise ValueError(f"{type} must not have quantity, price or split_ratio")

    if source == "import":
        if import_batch_id is None:
            raise ValueError("source 'import' requires import_batch_id")
    elif import_batch_id is not None:
        raise ValueError("import_batch_id is only allowed with source 'import'")
    if source == "proposal":
        if proposal_id is None:
            raise ValueError("source 'proposal' requires proposal_id")
    elif proposal_id is not None:
        raise ValueError("proposal_id is only allowed with source 'proposal'")

    if session.get(Account, account_id) is None:
        raise LookupError(f"account {account_id} not found")
    security = None
    if security_id is not None:
        security = session.get(Security, security_id)
        if security is None:
            raise LookupError(f"security {security_id} not found")
    if import_batch_id is not None and session.get(ImportBatch, import_batch_id) is None:
        raise LookupError(f"import batch {import_batch_id} not found")
    if proposal_id is not None and session.get(Proposal, proposal_id) is None:
        raise LookupError(f"proposal {proposal_id} not found")

    if type in _POSITION_TYPES and security is not None and security.currency != currency:
        raise ValueError(
            f"{type} currency {currency} does not match security {security_id} "
            f"currency {security.currency}"
        )

    if natural_key is not None:
        taken = session.scalar(
            select(Transaction.id).where(Transaction.natural_key == natural_key)
        )
        if taken is not None:
            raise ValueError(f"natural_key {natural_key!r} is already used by transaction {taken}")

    return Transaction(
        account_id=account_id,
        security_id=security_id,
        type=type,
        quantity=quantity_d,
        price=price_d,
        amount=amount_d,
        currency=currency,
        split_ratio=ratio_d,
        trade_date=trade_date,
        source=source,
        import_batch_id=import_batch_id,
        proposal_id=proposal_id,
        natural_key=natural_key,
        note=note,
    )


def _check_never_negative(
    session: Session,
    *,
    remove: Iterable[Transaction] = (),
    add: Iterable[Transaction] = (),
) -> None:
    """Re-derive every affected (account, security) history with the change applied.

    Read-only. ``remove`` rows are left out of the history; ``add`` rows are
    appended unsaved (id None sorts last within their date). Only position types
    with a security matter.

    Raises:
        ValueError: The derivation fails, e.g. a position would go negative.
    """
    remove = list(remove)
    add = list(add)
    pairs = {
        (r.account_id, r.security_id)
        for r in (*remove, *add)
        if r.type in _POSITION_TYPES and r.security_id is not None
    }
    removed_ids = {r.id for r in remove}
    for account_id, security_id in sorted(pairs):
        existing = session.scalars(
            select(Transaction).where(
                Transaction.account_id == account_id,
                Transaction.security_id == security_id,
                Transaction.voided_at.is_(None),
            )
        ).all()
        history = [r for r in existing if r.id not in removed_ids]
        history.extend(r for r in add if (r.account_id, r.security_id) == (account_id, security_id))
        positions.derive(history)


def _now_naive_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _get_live(session: Session, transaction_id: int) -> Transaction:
    row = session.get(Transaction, transaction_id)
    if row is None:
        raise LookupError(f"transaction {transaction_id} not found")
    if row.voided_at is not None:
        raise ValueError(f"transaction {transaction_id} is already voided")
    return row


def record_transaction(
    session: Session,
    *,
    account_id: int,
    type: str,
    amount: object,
    currency: str,
    trade_date: date,
    source: str,
    security_id: int | None = None,
    quantity: object = None,
    price: object = None,
    split_ratio: object = None,
    import_batch_id: int | None = None,
    proposal_id: int | None = None,
    natural_key: str | None = None,
    note: str | None = None,
) -> Transaction:
    """Validate and add one transaction; flush, never commit (the caller commits).

    Returns:
        The new, flushed Transaction (its id is set).

    Raises:
        TypeError: amount, quantity, price or split_ratio is a float, bool or
            unsupported type (INV-9).
        ValueError: A field breaks the per-type rules, the currency, source or
            id pairing rules, the security's currency, or natural_key
            uniqueness; or the row would make a position negative on any date.
        LookupError: The account, security, import batch or proposal does not exist.
    """
    row = _build(
        session,
        account_id=account_id,
        type=type,
        amount=amount,
        currency=currency,
        trade_date=trade_date,
        source=source,
        security_id=security_id,
        quantity=quantity,
        price=price,
        split_ratio=split_ratio,
        import_batch_id=import_batch_id,
        proposal_id=proposal_id,
        natural_key=natural_key,
        note=note,
    )
    _check_never_negative(session, add=[row])
    session.add(row)
    session.flush()
    return row


def void_transaction(session: Session, *, transaction_id: int) -> Transaction:
    """Void a live transaction by setting ``voided_at``; flush, never commit.

    The row is kept for history and ignored by position derivation. Refused if
    removing it would make a position negative on any date.

    Returns:
        The voided Transaction.

    Raises:
        LookupError: No transaction has this id.
        ValueError: The transaction is already voided, or voiding it would make
            a position negative.
    """
    row = _get_live(session, transaction_id)
    _check_never_negative(session, remove=[row])
    row.voided_at = _now_naive_utc()
    session.flush()
    return row


def void_and_replace(
    session: Session, *, transaction_id: int, **fields: object
) -> Transaction:
    """Correct a transaction: void the old row and add its replacement; flush, never commit.

    ``fields`` are the keyword arguments of ``record_transaction`` (all of its
    required ones). The new row's ``replaces_id`` points at the old row. Every
    affected position (the old row's and the new row's, which may differ) is
    checked in one pass, so nothing changes if either would go negative.

    Returns:
        The NEW Transaction.

    Raises:
        LookupError: No transaction has this id, or a referenced account,
            security, import batch or proposal does not exist.
        TypeError: As for ``record_transaction``; also an unexpected keyword
            (``replaces_id`` is not accepted).
        ValueError: The old row is already voided, the new fields are invalid,
            or the change would make a position negative. natural_key must
            differ from the old row's, which stays in the table.
    """
    old = _get_live(session, transaction_id)
    new = _build(session, **fields)  # type: ignore[arg-type]
    _check_never_negative(session, remove=[old], add=[new])
    old.voided_at = _now_naive_utc()
    new.replaces_id = old.id
    session.add(new)
    session.flush()
    return new
