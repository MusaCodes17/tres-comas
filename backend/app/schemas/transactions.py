"""Transaction and position schemas.

INV-6: request bodies forbid extra fields, so ``source``, ``import_batch_id``,
``proposal_id`` and ``natural_key`` cannot be sent. INV-9: decimal inputs are
``str`` (a JSON number is a 422) and decimal outputs are strings.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.models import Transaction
from app.schemas import dec_str
from app.services.positions import Position

TransactionType = Literal[
    "buy",
    "sell",
    "dividend",
    "deposit",
    "withdrawal",
    "fee",
    "split",
    "transfer_in",
    "transfer_out",
]


class TransactionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: TransactionType
    amount: str
    currency: str
    trade_date: date
    security_id: int | None = None
    quantity: str | None = None
    price: str | None = None
    split_ratio: str | None = None
    note: str | None = None


class TransactionReplace(TransactionCreate):
    account_id: int


class TransactionOut(BaseModel):
    id: int
    account_id: int
    security_id: int | None
    security_ticker: str | None
    security_exchange: str | None
    type: str
    quantity: str | None
    price: str | None
    amount: str
    currency: str
    split_ratio: str | None
    trade_date: date
    source: str
    import_batch_id: int | None
    proposal_id: int | None
    voided_at: datetime | None
    replaces_id: int | None
    note: str | None
    created_at: datetime

    @classmethod
    def from_row(cls, row: Transaction) -> "TransactionOut":
        sec = row.security
        return cls(
            id=row.id,
            account_id=row.account_id,
            security_id=row.security_id,
            security_ticker=sec.ticker if sec else None,
            security_exchange=sec.exchange if sec else None,
            type=row.type,
            quantity=dec_str(row.quantity),
            price=dec_str(row.price),
            amount=dec_str(row.amount),
            currency=row.currency,
            split_ratio=dec_str(row.split_ratio),
            trade_date=row.trade_date,
            source=row.source,
            import_batch_id=row.import_batch_id,
            proposal_id=row.proposal_id,
            voided_at=row.voided_at,
            replaces_id=row.replaces_id,
            note=row.note,
            created_at=row.created_at,
        )


class PositionOut(BaseModel):
    account_id: int
    security_id: int
    ticker: str
    exchange: str
    currency: str
    quantity: str
    total_cost: str
    average_cost: str | None
    realised_gain: str

    @classmethod
    def from_position(cls, pos: Position, *, ticker: str, exchange: str) -> "PositionOut":
        return cls(
            account_id=pos.account_id,
            security_id=pos.security_id,
            ticker=ticker,
            exchange=exchange,
            currency=pos.currency,
            quantity=dec_str(pos.quantity),
            total_cost=dec_str(pos.total_cost),
            average_cost=dec_str(pos.average_cost),
            realised_gain=dec_str(pos.realised_gain),
        )
