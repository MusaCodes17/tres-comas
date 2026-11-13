"""Account rules: create, list, edit. There is no delete.

Job: nickname uniqueness and normalisation. Accounts carry a nickname and a
broker label only (INV-8). ``base_currency`` is fixed at creation.

Callers own the commit; functions flush.
"""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account

ACCOUNT_TYPES = ("tfsa", "rrsp", "non_registered", "cash")
_CURRENCY_RE = re.compile(r"[A-Z]{3}")


def _clean_nickname(nickname: str) -> str:
    nickname = nickname.strip()
    if not nickname:
        raise ValueError("nickname must not be empty")
    return nickname


def _check_type(type: str) -> None:
    if type not in ACCOUNT_TYPES:
        raise ValueError(f"type must be one of {ACCOUNT_TYPES}, got {type!r}")


def list_accounts(db: Session) -> list[Account]:
    """All accounts, oldest first."""
    return list(db.scalars(select(Account).order_by(Account.id)))


def create_account(
    db: Session,
    *,
    nickname: str,
    type: str,
    base_currency: str = "CAD",
    broker_label: str | None = None,
) -> Account:
    """Create an account; flush, never commit.

    Raises:
        ValueError: Empty or duplicate nickname, bad type or currency.
    """
    nickname = _clean_nickname(nickname)
    _check_type(type)
    if not _CURRENCY_RE.fullmatch(base_currency):
        raise ValueError(f"base_currency must be three uppercase letters, got {base_currency!r}")
    if db.scalar(select(Account.id).where(Account.nickname == nickname)) is not None:
        raise ValueError(f"an account named {nickname!r} already exists")
    row = Account(
        nickname=nickname, type=type, base_currency=base_currency, broker_label=broker_label
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return row


def update_account(
    db: Session,
    *,
    account_id: int,
    nickname: str | None = None,
    type: str | None = None,
    broker_label: str | None = None,
) -> Account:
    """Edit nickname, type or broker label (None leaves a field unchanged); flush, never commit.

    Raises:
        LookupError: Unknown account id.
        ValueError: Empty or duplicate nickname, or bad type.
    """
    row = db.get(Account, account_id)
    if row is None:
        raise LookupError(f"account {account_id} not found")
    if nickname is not None:
        nickname = _clean_nickname(nickname)
        other = db.scalar(
            select(Account.id).where(Account.nickname == nickname, Account.id != account_id)
        )
        if other is not None:
            raise ValueError(f"an account named {nickname!r} already exists")
        row.nickname = nickname
    if type is not None:
        _check_type(type)
        row.type = type
    if broker_label is not None:
        row.broker_label = broker_label
    db.flush()
    return row
