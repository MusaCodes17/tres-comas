"""Security rules: create and list. Identity is ticker plus exchange.

Callers own the commit; functions flush.
"""

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Security

SECURITY_KINDS = ("stock", "etf", "cash")
_CURRENCY_RE = re.compile(r"[A-Z]{3}")


def list_securities(db: Session) -> list[Security]:
    """All securities ordered by ticker then exchange."""
    return list(db.scalars(select(Security).order_by(Security.ticker, Security.exchange)))


def create_security(
    db: Session,
    *,
    ticker: str,
    exchange: str,
    currency: str,
    kind: str,
    name: str | None = None,
    sector: str | None = None,
) -> Security:
    """Create a security; flush, never commit.

    Raises:
        ValueError: Empty ticker or exchange, bad currency or kind, or the
            (ticker, exchange) pair already exists.
    """
    ticker = ticker.strip().upper()
    exchange = exchange.strip().upper()
    if not ticker or not exchange:
        raise ValueError("ticker and exchange are required")
    if not _CURRENCY_RE.fullmatch(currency):
        raise ValueError(f"currency must be three uppercase letters, got {currency!r}")
    if kind not in SECURITY_KINDS:
        raise ValueError(f"kind must be one of {SECURITY_KINDS}, got {kind!r}")
    taken = db.scalar(
        select(Security.id).where(Security.ticker == ticker, Security.exchange == exchange)
    )
    if taken is not None:
        raise ValueError(f"security {ticker} on {exchange} already exists")
    row = Security(
        ticker=ticker, exchange=exchange, currency=currency, kind=kind, name=name, sector=sector
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return row
